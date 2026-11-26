# Proposed evaluation plan for synthetic v1.2

Keep the ChatGPT fixture pairs, the seeded Python outputs, and any future measured records in their own datasets. Use ChatGPT fixtures for integration checks and reviewer practice. Use independently collected measured data for any later claims about performance outside the synthetic prototype.

## Freeze the split before reviewing labels

The review tool first joins scenario families that share any generated session or any exact 15-feature combination. Then it assigns each connected set of families to one partition. This prevents data leakage, where an evaluation example closely related to training data can make a model appear to generalize better than it does.

The seed-42 plan for v1.2 assigns 560 observations to train, 220 to validation, and 220 to test, with 56, 22 and 22 generated sessions respectively. The 144-case blind review includes 66 train, 39 validation and 39 test cases. Keep the split manifest private during blind review. Fit any preprocessing, class weighting, resampling, and model only on the training partition. Use validation for method and threshold decisions. Reserve test for a final reported comparison after the plan and rubric are approved.

## Which classes can be assessed?

All six contextual recommendation classes and all six draft-rubric classes appear in every partition. In the review sample, each class for each source has at least six distinct feature vectors across at least two generated sessions in every partition. These are planning counts based on suggestions. Before evaluation, recompute class support using independently reviewed labels. If coverage drops, report the gap, expand the reviewed sample from eligible independent groups, or limit the metrics for that class.

An additional check ignores differences in Module 2 confidence. Only 92 validation and 71 test rows have a remaining feature pattern absent from earlier partitions. Each of these stricter subsets represents only three of the six draft classes. A six-class claim about unfamiliar evidence patterns therefore needs new scenario families and independent labels. Report this stricter check separately from the full synthetic split. Keep sensitivity checks grouped by session or family and avoid interpreting similar generated examples as independent measurements.

## Reduce manual review while preserving provenance

Start with the 144 blind cases. Record one independent judgment and review any disagreements before approval. If an approved prototype later uses draft-rubric suggestions for the rest of the synthetic training data, store those suggestions and the rubric version separately. Keep these provisional labels out of the independently labeled validation and test metrics. Compare the contextual and classification-only baselines against the same independent labels used to assess the models. Report counts and class-level errors along with aggregate metrics.

Model training remains a separate approval step.
