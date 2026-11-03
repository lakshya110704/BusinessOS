# BusinessOS — Product Vision & Build Plan

> This is the north star for what we're building, and the concrete first refactor
> to get there. Written after mapping the codebase (see `graphify-out/graph.html`).

---

## 1. The idea, in one paragraph

**BusinessOS is an AI business partner for any SMB that acts on memory and data,
not just the owner's gut.** It sits on top of how a business *already* operates —
orders from **vendors** and **customers**, arriving by **WhatsApp or phone call** —
captures all of it with zero extra effort, remembers everything, and uses that
memory to (a) keep the books (orders, khata/udhaar, stock), (b) act on the owner's
behalf with confirm-before-act, and (c) **answer any question the owner asks**:
*"aaj ki sales kitni hui?", "kitna stock order karna chahiye?", "pichle hafte jo
order kiya usme se kitna bika?"*

The thesis in one line: **the system should eventually know the business better
than the owner's memory does — and the owner just talks to it.**

## 2. Who it's for

Any small shopkeeper / trader — kirana, general store, wholesaler, supplier,
manufacturer. Not vertical-locked. The same engine already handled textile vendor
orders and kirana customer orders with no fundamental change.

## 3. The core thesis: acts on memory + data

Three incumbents define the gap:
- **Khatabook / OkCredit** — digital ledgers that require **manual typing**. Accounts
  go stale. BusinessOS captures automatically from how they already communicate.
- **AI Kirana** — an **AI bot answers the call** and takes instant UPI. It replaces
  the human and assumes instant payment. BusinessOS **keeps the human** and handles
  **monthly udhaar**, the way trade actually runs.

Our edge is **effortless capture + a memory that compounds**, surfaced through one
conversational interface the owner already lives in (WhatsApp).

## 4. The unifying model (the key insight)

Everything collapses into **one idea: every event is an order with a direction.**

```
PURCHASE  (vendor → business, "itna raw material bhej do")   → stock IN,  a payable
SALE      (customer → business, "2 kg cheeni bhej do")       → stock OUT, a receivable

current stock (per item) = Σ purchases − Σ sales       ← DERIVED, never counted by hand
who owes me (khata)      = Σ unpaid sales per contact
what I owe               = Σ unpaid purchases per vendor
```

So we do **not** build a separate inventory system. Stock, "ordered vs sold", and
reorder signals are all *computed views* over the two order streams. The one thing
that makes the math work is an **item catalog** that canonicalizes messy item names
and units ("cheeni" = "sugar" = "Tata sugar 1kg") so purchases and sales net.

On top of that data sits the **assistant**: the owner asks in Hindi/Hinglish, a
tool-calling agent runs safe queries over the data and answers — and can also *act*
(routing into the existing confirm-before-act loop).

```
INPUTS                 UNDERSTAND            MEMORY (soul)          ACT / ANSWER
WhatsApp (text+voice)  intent → entities →   relational memory +   confirm-before-act →
phone calls            line items →          item catalog →        execute  |  assistant
                       context enrich        derived stock/khata   answers any question
```

## 5. Current state (from the code graph)

Mapped: **399 nodes, 868 edges, 30 communities.** What exists and works today:

- ✅ **Spine:** `route()` is the pipeline hub — webhook → router → classify →
  extract → enrich → generate → confirm → execute. Proven live.
- ✅ **Confirm-before-act engine**, **WhatsApp channel** (text + voice/Whisper),
  **repos** (business/contact/message/order/payment/task/pending_confirmation),
  **scheduler** (daily summary, payment reminders).
- 🟡 **Orders already have `direction` and `items JSONB`** in the schema — but
  `direction` is hardcoded `"incoming"` and `items` is synthesized as a *single*
  line from flat entity fields.
- 🟡 **Calls:** a concierge tester (`scripts/concierge_call_orders.py`) transcribes
  recordings → orders + khata, but calls aren't a first-class channel yet.
- ❌ **Line-item extraction** (multi-item orders), **item catalog**, **derived
  stock**, **the assistant query interface**, **semantic memory** (the
  `messages.embedding` column is unused).

`get_supabase()` is the god node (48 edges) — every repo depends on it; that's the
clean data boundary everything new will sit behind.

## 6. Build roadmap (phased)

1. **Spine** — make `direction` meaningful (purchase/sale) and orders carry real
   **line items**. Foundation for everything.
2. **Item catalog** — canonicalize item names + units per business, so streams net.
3. **Derived stock & khata** — compute stock, outstanding, reorder from the orders.
4. **The assistant** — owner asks anything on WhatsApp → tool-calling agent over the
   data → answers (and can act via confirm).
5. **Calls as a first-class channel** — promote the concierge path into the pipeline.
6. **Semantic memory** — populate embeddings + recall, so the enricher and the
   assistant draw on past conversations, not just structured rows.
7. **Owner dashboard** — a web cockpit to *see* the OS.

---

## 7. The spine refactor (step 1) — concrete, grounded in the code

### 7a. `direction` → purchase / sale (not hardcoded)

`app/core/action_executor.py::_create_order` today:
```python
"direction": "incoming",          # ← hardcoded
```
Change: derive it. Introduce a `role` on the contact (`vendor` | `customer`) or
infer from the flow, and set:
```python
"direction": "purchase" if contact_role == "vendor" else "sale",
```
- `purchase` = business buying from a vendor (stock IN, a payable)
- `sale`     = business selling to a customer (stock OUT, a receivable)

Migration note: backfill existing `"incoming"` rows to the right value (a small
`004_order_direction.sql`), and standardize the vocabulary (`payment_repo` also
hardcodes `direction="receivable"` — align it: sale→receivable, purchase→payable).

### 7b. Orders carry real line items (the real gap)

Today the extractor returns ONE item and the executor wraps it in a 1-element list:

`app/core/entity_extractor.py` — `EntityResult` is flat:
```python
quantity: Optional[int]; unit: Optional[str]; sku: Optional[str]   # one item only
```
`action_executor._create_order`:
```python
"items": [{"quantity": fields.get("quantity"), "unit": fields.get("unit"),
           "description": fields.get("sku")}],                      # collapses multi-item
```
Change: make line items first-class end to end.
```python
# entity_extractor.py
class LineItem(BaseModel):
    item: str                      # free text as heard ("cheeni")
    canonical_id: Optional[str] = None   # filled by the item catalog (7c)
    quantity: Optional[float] = None
    unit: Optional[str] = None

class EntityResult(BaseModel):
    items: list[LineItem] = Field(default_factory=list)   # ← the change
    amount: Optional[float] = None
    delivery_date: Optional[str] = None
    payment_terms: Optional[str] = None
    contact_name: Optional[str] = None
    confidence: str = "LOW"
    ambiguities: list[str] = Field(default_factory=list)
```
The extraction prompt already produces an items list in
`scripts/concierge_call_orders.py` — reuse that shape in `app/ai/prompts/order_parser.txt`.
Then `action_generator._entity_fields` passes `items` through, and
`_create_order` stores `fields["items"]` directly instead of synthesizing one.
(Keep accepting the old flat fields during transition → map single item into the list.)

### 7c. Item catalog (enables netting) — new, small

New table + repo: per-business canonical items.
```sql
-- 005_item_catalog.sql
CREATE TABLE item_catalog (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id),
  canonical_name TEXT NOT NULL,      -- "sugar"
  base_unit TEXT,                    -- "kg"
  aliases JSONB DEFAULT '[]',        -- ["cheeni","sugar","tata sugar"]
  UNIQUE (business_id, canonical_name)
);
```
A normalizer (LLM-assisted, cached) maps each `LineItem.item` → `canonical_id`,
growing the catalog as new items appear. This is also a quiet moat: the business's
own normalized product map.

### 7d. Derived stock & khata — no new storage, just queries

`order_repo` (or a new `stock_repo`) computes from the two streams:
```python
async def stock_for_business(business_id) -> dict[str, float]:
    # Σ purchase line qty − Σ sale line qty, grouped by canonical_id
async def outstanding_receivables(business_id) -> list:   # unpaid sales per contact (khata)
async def reorder_candidates(business_id) -> list:        # low derived stock + outflow rate
```

### 7e. The assistant route — new module + one router branch

`message_router.route()` already splits owner messages (confirm taps) from contact
messages. Add: when the **owner** sends free-form text that isn't a tap → new intent
`business_query` → `app/core/assistant.py`.

```python
# app/core/assistant.py  (new)
TOOLS = [sales_summary, order_history, outstanding_receivables,
         stock_for_business, reorder_candidates, contact_lookup]
async def answer(owner_question: str, business_id: str) -> str:
    # openai tool-calling: LLM picks tool(s) → run real queries → phrase in Hindi
```
Extend `app/ai/openai_client.py` with a `complete_with_tools()` helper (function-
calling), mirroring the existing `complete_json()`. Read-only queries need no
confirmation; if the owner asks it to *do* something, route that into the existing
`confirm_engine`.

### What NOT to do
- Don't build a separate inventory system — stock is derived (§4).
- Don't widen to "OS for everything" in code before the spine works end to end.
- Don't break the live WhatsApp loop — add alongside, migrate behind the flat-field
  fallback, keep confirm-before-act intact.

---

## 8. First concrete PR
**"Line items + real direction"** (7a + 7b): the smallest change that makes both
vendor and customer, multi-item orders first-class — and unlocks catalog → stock →
the assistant. Everything else sits on it.
