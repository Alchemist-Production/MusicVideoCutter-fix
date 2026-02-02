## 2025-02-18 - Gradio File Component Limitation
**Learning:** The `gr.File` component in Gradio does not support the `info` argument for helper text, unlike other components like `gr.Textbox` or `gr.Slider`.
**Action:** When adding instructions for file uploads, rely on the `label` or add descriptive Markdown text above/below the component instead of using the `info` parameter.
