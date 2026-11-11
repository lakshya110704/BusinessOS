# BusinessOS: Product Vision and Build Plan

> The north star for what we are building, and an honest account of how far the code
> has got. Status below comes from the code and real runs (last checked 2026-11-12).
> For the data flow and the gated plan to a calls product, see [PIPELINE.md](PIPELINE.md).

---

## 1. The idea, in one paragraph

**BusinessOS is an AI business partner for any small business that acts on memory and
data, not just the owner's gut.** It sits on top of how a business already operates:
orders from customers and vendors, arriving by WhatsApp or phone call. It captures all
of it with zero extra effort, remembers everything, and uses that memory to (a) keep
the books (orders, khata/udhaar, stock), (b) act on the owner's behalf with
confirm-before-act, and (c) answer any question the owner asks: "aaj ki sales kitni
hui?", "kitna stock order karna chahiye?", "pichle hafte jo order kiya usme se kitna
bika?"

The thesis in one line: **the system should eventually know the business better than
the owner's memory does, and the owner just talks to it.**

## 2. Who it is for

Any small shopkeeper or trader: kirana, general store, wholesaler, supplier,
manufacturer. Not vertical-locked. We enter through kirana shops, where the pull signal
was strongest (owners want help tracking phone orders).

## 3. The core thesis: acts on memory and data

Two incumbents define the gap:
- **Khatabook / OkCredit**: digital ledgers that require manual typing. Accounts go
  stale. BusinessOS captures automatically from how owners already communicate.
- **AI Kirana**: an AI bot answers the call and takes instant UPI. It replaces the human
  and assumes instant payment. BusinessOS keeps the human and handles monthly udhaar,
  the way trade actually runs.

Our edge is **effortless capture plus a memory that compounds**, surfaced through one
conversational interface the owner already lives in (WhatsApp).

**Calls are the core bet.** Owners say most orders arrive by phone call, not WhatsApp.
The product does not stand on WhatsApp alone. The plan is to capture the owner's own
call recordings (the dialer already saves them), not to put a bot on the line.

## 4. The unifying model

Everything collapses into one idea: **every event is an order with a direction.**

```
SALE      (customer -> business, "2 kg cheeni bhej do")      stock OUT, a receivable
PURCHASE  (business -> vendor,   "50 kg cheeni bhej do")     stock IN,  a payable

current stock (per item) = sum of purchases - sum of sales    (derived, never counted)
who owes me (khata)      = sum of unpaid sales per contact
what I owe               = sum of unpaid purchases per vendor
```

Reality check: an incoming message is a customer buying from the shop, so inbound is
always a **sale**. Purchases are placed by the shop through outgoing messages and calls,
which the inbound pipeline never sees. So only the sale side exists today. Stock and
payables stay unbuilt until purchase capture exists.

We do not build a separate inventory system. Stock, "ordered vs sold" and reorder
signals will be computed views over the two order streams. The thing that makes the
math work is an item catalog that canonicalizes messy item names and units
("cheeni" = "sugar" = "Tata sugar 1kg").

```
INPUTS                 UNDERSTAND            MEMORY                 ACT / ANSWER
WhatsApp (text+voice)  intent -> entities -> relational memory +    confirm-before-act ->
phone calls (planned)  line items ->         item catalog (planned) execute | assistant
                       context enrich        derived stock (planned)  answers questions
```

## 5. Current state (code and real runs)

Legend: **Run** = executed for real. **Mocked** = passes tests with mocks only.
**Built** = code exists, never run. **Missing** = not built.

| Piece | Status | Evidence |
|---|---|---|
| WhatsApp webhook (HMAC verify, Redis dedup, fast ack) | Mocked | test_webhook; real inbound blocked by Meta dev mode |
| Intent + entity extraction, multi-item `LineItem`s | Mocked | 31 tests pass, 5 skipped (need live keys) |
| Confirm-before-act (owner taps 1/2/3) | Mocked | real taps do not route back in dev mode |
| Executor: order, contact stats, payment reminder task | Mocked | a documented live write (ORD-2026-002, 2026-09-21) was not re-run |
| Direction on orders | Built | explicit `"sale"` for every inbound order (BOS-56) |
| Voice note to Hindi transcript (Whisper) | Run | concierge run, 0 failures |
| Owner assistant (BOS-49) | Run, seeded data only | tool-calling over `sales_summary`, `pending_udhaar`, `recent_orders`; answered over 5 orders I seeded, no real business data |
| Daily summary 8 PM, payment reminders 9 AM | Built | scheduler jobs exist, never run; proactive sends need approved WhatsApp templates |
| Concierge call tester | Run, clean clips only | 3 WhatsApp voice notes, 1 order parsed, confidence 0.90; never run on real noisy calls |
| Calls as an ingested channel | Missing | only the batch script exists |
| Item catalog, derived stock, reorder | Missing | |
| Purchase (outbound) capture | Missing | |
| Semantic memory (`messages.embedding`) | Missing | column exists, unused |
| Owner dashboard | Missing | |

## 6. Roadmap

1. **Spine: line items and direction.** Done. Orders carry a list of items; inbound is
   always a sale.
2. **The assistant.** Done for sales, udhaar and recent orders. Stock and reorder tools
   wait for the catalog.
3. **Calls: validate, then build.** Now. Gate: run the concierge tester on about 10
   real, messy order calls and read the accuracy (BOS-55). Only if capture holds up,
   build the thin wrapper (recording folder in, a correctable order list out) (BOS-52).
   No telephony or IVR bot.
4. **Item catalog.** Canonicalize item names and units per business so streams net.
5. **Derived stock and reorder.** Computed from orders, never counted by hand.
6. **Purchase capture.** Outgoing messages and calls, so payables and stock-in exist.
7. **Semantic memory.** Populate embeddings so the enricher and assistant can recall
   past conversations.
8. **Owner dashboard.** A web view of the whole system.

## 7. What shipped and what changed from the original plan

### Direction: decided differently

The first plan derived direction from a contact's role (vendor means purchase,
customer means sale). BOS-56 overruled that: owners confirmed that incoming messages
are almost always sales, and purchases are mostly outgoing. So the executor sets
`direction = "sale"` explicitly and `payment_repo` records receivables. No classifier,
no role lookup. Purchases return with outbound capture (step 6).

### Line items: shipped

`EntityResult.items` is a list of `LineItem(description, quantity, unit)`. The executor
stores the list in `orders.items`; the flat `quantity/unit/sku` fields mirror the first
item for older callers. Not done: `canonical_id` on items (needs the catalog).

### Item catalog: not built

Planned shape: a per-business table of canonical names, base units and aliases, plus an
LLM-assisted, cached normalizer that grows it as new items appear. It is also a quiet
moat, since it becomes the business's own normalized product map.

### Derived stock and khata: partly built

The khata exists as unpaid sales per contact (the assistant's `pending_udhaar` reads
it). Derived stock and reorder candidates need the catalog and purchase capture first.

### The assistant: shipped for sales data

`app/core/assistant.py` is a tool-calling agent over read-only repo queries, reached
when the owner texts the business line (sender equals the business phone). It answers
in Hindi/Hinglish from real rows and never invents numbers. If the owner asks it to do
something, that should route into the existing confirm engine; that part is not built.

### What not to do

- Do not build a separate inventory system. Stock is derived (section 4).
- Do not build a telephony or IVR channel. It breaks the human-relationship wedge.
- Do not build the calls wrapper before capture is proven on real recordings.
- Do not break the live WhatsApp loop. Keep confirm-before-act intact.
