# Prompt log

## 2026-11-24

- Asked: Update `spec.md` to describe a Python desktop app using Tkinter, without building anything.
- Changed: Reworked the platform and presentation requirements in `spec.md` for a local Tkinter desktop application. No app implementation was created.
- Worked: Yes; the spec now identifies Python and Tkinter as the target platform.

## 2026-11-24

- Asked: Read `spec.md` and build the desktop app it describes, using `index.html` as a behavior reference.
- Changed: Added the Tkinter beam calculator in `beam_designer.py`, embedded the catalog with AISC v15.0 provenance in `01_data/beam-catalog-source.md`, and implemented beam/load inputs, analysis, checks, and Canvas diagrams.
- Worked: Implementation is complete; the app was not launched in this turn.

## 2026-11-24

- Asked: Run all validation cases in `spec.md` against the app calculations and compare expected with actual values.
- Changed: Ran the three cases through `beam_designer.solve()`; appended this request to the log.
- Worked: Yes. Reactions and moments matched, and calculated deflections matched the spec approximations within rounding.

## 2026-11-24

- Asked: Add File menu Save and Open for beam designs, and remove saving designs from the spec's out-of-scope section first.
- Changed: Added save and open requirements to the spec (saving was already absent from out of scope), and implemented JSON save and open with validation and recalculation in the Tkinter app.
- Worked: Yes. Checked a Tkinter save/open round trip with both load types, recalculation, invalid and malformed files, and cancellation.

## 2026-11-24

- Asked: Add a button to export a table of x, V, M, and deflection along the beam to an Excel-compatible CSV file.
- Changed: Added a CSV export button, sampling positions along the beam and including load events, extrema, and both sides of shear jumps; updated the spec.
- Worked: Yes. Checked the exported midpoint moment and deflection, shear jump values, recalculation after edits, invalid inputs, cancellation, and UTF-8 Excel compatibility.

## 2026-11-24

- Asked: Add a button that saves the inputs, diagrams, and checks as a PDF calculation sheet.
- Changed: Added a self-contained vector PDF export, documented the feature in the spec, and aligned diagram peak markers with the plotted values.
- Worked: PDF generation passed checks for the expected calculation content, document structure, long load lists, invalid inputs, and cancellation. The PDF was not visually inspected in a PDF viewer.

## 2026-11-24

- Asked: Write a short README describing the app, required packages, and the command to start it.
- Changed: Added `README.md` with the app's purpose, Python and Tkinter requirements, and launch command.
- Worked: Yes. Confirmed the requirements and command against the app's imports and entry point.
