# Pre-retest diagnosis

Observed R2 v1 failure (not a hypothetical test): output had a ninth module transfer_failure; two verbatim quotations were assigned to wrong pages. The reframing quote assigned to p2 occurs on p3, and the transfer_failure quote assigned to p9 occurs on p3. Other quotes matched OCR after whitespace normalization. The single composite judgment about causal identification also mixed source-supported author concessions with analyst inference.

Main bottleneck: source attribution is underspecified at the individual-judgment level. A quote can exist and still be wrongly located or fail to support every assertion in a compound judgment. R0/R1 already correctly state the main research questions, so improving basic question identification is not the observed need.

Change hypothesis: explicitly separate author claims from analyst inference, require checking passage IDs and keep one evidence level per judgment. Retain all eight modules, move any failure example inside transfer, limit to one judgment per module. Re-run once on exactly the frozen paper and exemplar material, with unchanged model and output-token cap. Do not give the target answer or corrected page mappings to the model.

Success criterion: the complete raw revised output passes the existing strict schema and quote-location checks and source-based review finds fewer attribution errors. Not a success criterion: more fields, higher LLM self-score or longer text. Even if source attribution improves, this does not establish deeper scientific understanding or generalization. Failure and content lost through compression must remain visible.
