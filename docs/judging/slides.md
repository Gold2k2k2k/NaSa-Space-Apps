# Seven-slide internal outline

This is an English presentation outline. Confirm the actual 2026 submission
format and time limit; seven slides is our proposal, not a current official rule.

1. **A manager's question.** Which recorded periods deserve closer review before
   planning land or forest management? Explain the cost of confusing sensor
   counts with physical fires. No measured user impact yet.
2. **Why counts change.** MODIS and VIIRS sample differently. Show raw versus
   harmonized series. Explain confidence-weighted occupancy, HHE and the limits
   of sensor agreement in one sentence each.
3. **One real NASA case.** Central Highlands rectangle, Vietnam; 2001–2024;
   16,258 original detection rows. Show the map, source badge and manifest.
   State that the rectangle is not an administrative or forest boundary.
4. **An inspectable comparison.** Train both factors on 2013–2020, assess
   2021–2024, keep the available 2001–2020 descriptive reference. Show κ and the
   independently fitted FRP factor, paired sample counts and exclusions.
5. **Report the limits.** Occupancy held-out R² 0.841, efficiency 0.787; FRP
   efficiency −5.058 on 35 pairs. Keep **UNVERIFIABLE** visible. Missing coverage
   is not zero activity, and agreement is not ground truth.
6. **Complete the manager's task.** Choose actual data → review February/March/
   January → open the manager brief → retain the receipt and audit ZIP. Demonstrate
   one source-preserving experiment and offline verification.
7. **What follows.** Independent incident/coverage validation and land-manager
   usability testing. Cite NASA, methods, dependencies, font licenses and AI
   assistance. Public access and final submission require owner action.

Suggested live sequence (internal rehearsal, no official duration claim): start
the local server; choose the NASA case; inspect February 2024 and its reference
support; switch raw/harmonized; inspect held-out occupancy and FRP; open the brief;
download an audit ZIP and show `python -S -B verify.py receipt.json` returning VALID.
Explain that VALID means internal reproducibility, not authenticating NASA or
certifying the science. Use the [results](results/model-evaluation.json) if a live
environment is unavailable, labeling any screenshot as a recorded demonstration.
