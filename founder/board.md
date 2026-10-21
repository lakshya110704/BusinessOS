# Board summary — BusinessOS

Chair's summary of three memos in `founder/board/`. The lenses are summaries of published frameworks (Offers, Monopoly, Product); the members are not the authors and do not speak for them.

## The vote

**3 fund if, 0 pass, 0 fund. Average score: 5.0 / 10.**

| Lens | Score | Vote |
|---|---|---|
| Offers | 5 | FUND IF |
| Monopoly | 4 | FUND IF |
| Product | 6 | FUND IF |

Nobody passed, and nobody funded outright. Every member says the same thing in different words: the capture loop is real, but there is no evidence yet that a shop keeps using it.

## Risks more than one member raised (most important first)

1. **No real-shop evidence (all three).** There are no active or paying shops, the DB was wiped, and there is no retention data. The pitch's own stated goal is daily use, so this is the central gap. Offers: "likelihood is near zero." Monopoly: the memory moat "does not exist" until months of use. Product: nothing shows owners still tap in week four.
2. **The headline feature is not built (all three).** "Ask your business anything in Hindi" is what the pitch sells, but today only the capture loop exists. The daily-habit goal rests on something nobody has seen.
3. **Half the orders are phone calls, and call ingestion is not built (Offers, Product).** Books that miss half the orders are wrong from day one, and wrong books go stale like the paper diary.
4. **Meta platform dependency and dev-mode limits (all three).** Business Verification and Live mode are unresolved. Owner button taps don't route back, free-form messages need an open 24-hour window, and proactive messages need approved templates. Monopoly adds that Meta can change policy or pricing.
5. **The money is not tied to the product (Offers, Monopoly).** The product is free to the shopkeeper. Revenue depends on collections fees, NBFC lending and a network take-rate, none of which exist. Price, revenue per shop and cost to serve are missing.
6. **Distribution is asserted, not shown (Offers, Monopoly).** In-person, one cluster at a time is a go-to-market style, not evidence of how the first 100 shops arrive or what each costs.

Raised by one member only:
- **Offers:** no named outcome or guarantee; the offer is easy to copy on the surface.
- **Monopoly:** no durable advantage yet. Models are rented, the pipeline is reproducible in weeks, and incumbents (Khatabook, OkCredit) could add WhatsApp or voice capture. The network effect is asserted, not designed.
- **Product:** the confirm tap may become the new typing at dozens of orders a day. Rule 5 (never auto-execute) is in tension with "zero typing."

## Conditions (checklist for the rest of the pack)

**Evidence**
- [ ] Small pilot of real shops in one cluster, live on WhatsApp in Live mode, run for several weeks with a usage and retention threshold agreed up front. Owners still confirm orders and return unprompted in week four. *(Offers, Monopoly, Product; design the test with /founder-consumer)*
- [ ] Measured confirm-tap rate and error rate at real volume, with a lighter path for repeat orders. *(Product)*
- [ ] Voice and item accuracy on real shop speech, not the 50-message test corpus. *(Product)*

**Product**
- [ ] "Ask in Hindi" working on real captured data, even if narrow (today's sales, who owes me), before spending on lending, collections fees or the network. *(Offers, Product)*
- [ ] Close the phone-call gap, or show with pilot data that the call share is smaller than claimed. *(Offers, Product)*
- [ ] Decide the one thing version one does brilliantly, and what is cut to get there. *(Product)*

**Platform**
- [ ] Meta Business Verification and Live mode approved, templates working, plus a fallback channel or plan if Meta delays or restricts the use case. *(Offers, Monopoly, Product)*

**Money and market**
- [ ] One tested money path (most plausibly udhaar collections) with a real price or fee and an early read on cost to serve per shop. *(Offers, Monopoly; /founder-cfo)*
- [ ] Unit numbers: price or revenue per shop, CAC, API cost per shop, cluster size and density. *(all three; /founder-cfo, /founder-competitors, /founder-consumer)*
- [ ] Market sizing and an answer on what Khatabook/OkCredit users lose by switching. *(Offers, Monopoly; /founder-competitors)*
- [ ] A named, buildable advantage beyond rented models and a WhatsApp wrapper (owned order-history data and underwriting, or a concrete network mechanic), with a written answer on the incumbent response. *(Monopoly)*
- [ ] A named outcome and a guarantee the offer can stand behind. *(Offers)*
- [ ] Name the team. *(Monopoly)*

**Open numbers nobody has yet** (not invented here): price, revenue per shop, CAC, cost to serve, market size, cluster density, retention, voice accuracy on real speech, call share of orders.

## Where the members disagree

- **Strength of the position.** Product scores it highest (6) because the capture loop works and the "no typing" idea is sound. Monopoly scores it lowest (4) because a working loop on rented models is not a durable advantage. Offers sits between (5).
- **What to fix first.** Product wants the experience made trustworthy first (calls, tap fatigue, the Hindi answers). Monopoly wants a defensible asset and platform independence first. Offers wants proof that someone pays. They agree on the pilot, and the pilot is the only condition that serves all three.
- **Where the moat comes from.** Monopoly sees credit underwritten on verified order flow as the one place a real proprietary advantage could form. Offers sees lending as an untested money path. Neither is wrong; the memos do not resolve it.

## The strongest version of this business

The board sees a **narrower and earlier-revenue business than the one pitched.** It is a WhatsApp capture-and-khata tool for one neighbourhood cluster of kirana shops that does one thing well: it keeps the udhaar book complete without typing, and it chases what is owed. Collections is the first money path because it is the one tied directly to a pain the owner already named and to cash they can see. The "ask in Hindi" answers come next, narrow, on top of that data. Credit comes only after months of real order history exist to underwrite it, and the network graph comes after that, if ever. The pitch presents four layers (operations, collections, credit, network) as one story; the board would fund the first two and treat the last two as options earned by data. That differs from what was pitched, which asks for $2M against all four.

A pass is not the result here. The board's position is that the idea has a real pain and a working core, and has not yet shown it holds up with a real shop.

## Next step

`/founder-competitors` to see who else is within reach of the same buyer (Khatabook, OkCredit, the call-bots), or `/founder-consumer` to design the pilot test with simulated buyers.
