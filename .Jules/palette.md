## 2026-02-02 - [Clarifying Ambiguous Controls]
**Learning:** Users can misinterpret 'Intensity' when it inversely correlates to frequency (e.g. 1 = high intensity/every beat, 16 = low intensity).
**Action:** Use 'Interval' or 'Frequency' for time-based controls and explicitly state the relationship (e.g. 'Every Nth beat') in help text.

## 2026-02-02 - [Gradio Feedback]
**Learning:** Long-running processes in Gradio without 'gr.Progress' leave users uncertain if the app is frozen.
**Action:** Always add 'progress=gr.Progress()' to blocking functions and use 'gr.Info'/'gr.Error' instead of returning status strings.
