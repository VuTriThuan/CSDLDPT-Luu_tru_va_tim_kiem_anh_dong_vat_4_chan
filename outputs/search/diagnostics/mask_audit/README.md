# Query mask audit, 23 October 2026

Only query diagnostics were written. Source images, requirement 2 masks, B400
descriptors, SQLite database, normalizer, and application code were not changed
for this audit.

## Evidence

- [Source, query mask, normalized foreground, and approved mask](mask_comparison.png)
- [Same-bbox raw GrabCut versus morphology](morphology_ablation.png)
- [All 22 saved-query mask comparisons](query_mask_comparison.json)
- [Four-image morphology ablation](morphology_ablation.json)

An approved mask is the manually accepted mask used by the frozen B400 run.
IoU here measures agreement with that mask; it does not measure segmentation
accuracy because no independent ground-truth mask was supplied. Filename labels
were not used to judge visual retrieval relevance.

## Findings

1. `Camelus_bactrianus_0057.jpg` shows a large segmentation failure. Default
   GrabCut includes the adjacent tree stump and grass. Foreground occupies 50.3%
   of the image, with agreement IoU 0.4252 against its approved mask. After saved
   keep/remove strokes, foreground is 22.1%, agreement rises to 0.9182, and the
   closest displayed distance changes from 0.4454 to 0.2177. This is evidence
   that mask editing substantially changes visual retrieval. A smaller distance
   alone is not a relevance score.
2. `Canis_familiaris_0355.jpg` loses much of the face and neck and retains an
   adjacent patch of grass. Its agreement IoU is 0.6093. The normalized foreground
   consequently contains an incomplete animal and extra background. Existing
   mask statistics report `suspicious=no` for this mask and for the initial camel
   mask. These flags cannot establish that the object has been segmented well.
3. External `Bos_taurus_001.jpg` loses lower legs in grass. No exact-byte source
   hash matches the frozen B400 corpus, so no approved-mask comparison is made.
4. `Camelus_bactrianus_0008.jpg` loses lower leg sections; agreement is 0.8591.
   `Canis_familiaris_0470.jpg` has exactly the approved mask, so segmentation is
   not a complete explanation for the appearance of every saved result.
5. Of the 22 saved result folders for 23 October, 21 have default rectangle
   metadata `[10, 10, 556, 364]`; one loaded a mask. None records a user rectangle.
   The old GUI allows its “create mask from bbox” action with no drawn bbox,
   silently invoking this almost-full-frame default rectangle.
6. `validate_arrays` validates dimensions, binary values, and nonempty/nonfull
   foreground. It does not validate which pixels belong to the animal. The old
   “Mask hợp lệ” status conflates these different kinds of validity.

## Morphology ablation

The same RGB pixels, seed 0, default rectangle and 5 GrabCut iterations were used
in both variants. Morphology is the existing 5×5 ellipse, opening twice then
closing twice. All four regenerated morphology masks exactly match the original
saved query masks. B400 and the scaler remained frozen.

| Image | Raw/morph agreement IoU | Pixels removed/added | Raw→morph squared vector distance |
| --- | --- | --- | --- |
| Camel0057 | 0.4242 / 0.4252 | 510 / 130 | 0.01056 |
| Canis0355 | 0.6117 / 0.6093 | 896 / 225 | 0.23227 |
| Camel0008 | 0.8629 / 0.8591 | 237 / 98 | 0.22395 |
| External Bos001 | no approved match | 139 / 44 | 0.28718 |

Removing morphology does not restore the missing face or legs and does not
remove the tree/crop contamination. Morphology helps remove small disconnected
pixels, while sometimes also removing thin animal details. Its effect on ranking
is mixed in this sample.

Small pixel changes can create large descriptor changes because B400 crops to
the bounding box of every foreground component. Raw Camel0008 contains separate
2-pixel and 1-pixel components, changing bbox height from 304 to 343 pixels; raw
Bos001 contains a single detached pixel, changing bbox height from 206 to 281.
This changes the scale, padding, profile strips, and spatial cells of the whole
foreground. The saved data demonstrates sensitivity to mask geometry; it does
not establish that a raw mask is the better one.

The no-stroke “apply GrabCut” action can also change masks. Relative to the
initial saved Bos001 mask, two saved zero-stroke refinements differ in 727 and
723 pixels, with squared descriptor differences 0.03584 and 0.03573. Refinement
initializes all untouched pixels as probable classes and re-estimates GrabCut.

## Recommended application changes

- Make the drawn rectangle explicit before GUI mask generation. Include a small
  margin around the complete animal, keeping nearby objects outside when possible.
- Show foreground and overlay at a size suitable for checking head, ears, horns,
  feet, tail, and background. Treat binary validity as a format check and request
  visual review even when heuristic flags are absent.
- Expose disconnected foreground, tiny distant components, and substantial
  geometry/area changes as soft review hints. Do not claim mask quality from
  area ratio or component count alone.
- Require new strokes before the GUI refinement action. Keep/remove strokes
  work on the saved camel example and are the most direct correction.
- If cleanup becomes optional, preview its effect. Do not silently replace the
  morphology policy with raw GrabCut based on these four samples.
- Preserve B400/scaler and measure retrieval against human visual relevance
  judgments. Correct segmentation improves the query representation but does
  not make hand-crafted descriptors a semantic animal recognizer.
