# PeckTeX

<div align="center">
   <img src="docs/about/app.png" alt="PeckTeX Logo" width="128"/>
   <h3>AI-Driven Image to LaTeX Desktop Tool v1.0</h3>

   [![Version](https://img.shields.io/badge/Version-v1.0-orange.svg)](https://github.com/River-Du/PeckTeX/releases)
   [![AI Assisted](https://img.shields.io/badge/AI_Assisted-Development-blueviolet.svg)](#)
   [![Python >= 3.8](https://img.shields.io/badge/Python->=3.8-blue.svg)](https://www.python.org/)
   [![PySide6](https://img.shields.io/badge/PySide6-GUI-green.svg)](https://wiki.qt.io/Qt_for_Python)
   [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


   **English** | [简体中文](./README.md)


</div>

## Table of Contents

- [Project Introduction](#project-introduction)
- [Features](#features)
- [Interface and Views](#interface-and-views)
- [Dependencies and Startup](#dependencies-and-startup)
- [Standard Usage Workflow](#standard-usage-workflow)
- [Configuration Parsing](#configuration-parsing)
- [Project Architecture](#project-architecture)
- [Frequently Asked Questions (FAQ)](#frequently-asked-questions-faq)
- [License](#license)

## Project Introduction

**PeckTeX** is a lightweight desktop application built on the **Python** and **PySide6** frameworks. By invoking Vision Language Model (VLM) APIs, this application recognizes and converts content from images—such as mathematical formulas, chemical equations, handwritten derivations, and tables—into **LaTeX** or other markup language codes.

Core processing workflow:

```text
Screenshot/Paste/File Import -> VLM API Recognition -> Streaming Output -> HTML/KaTeX Preview
```

## Features

- **Convenient Image Input**: Supports desktop screen capture, system clipboard reading, local file selection/drag-and-drop, and loading from the built-in image folder.
- **Custom Recognition Functions**: Supports customizing various prompts for core requests. Built-in templates include LaTeX mathematical formulas, MathML mathematical formulas, handwriting recognition, chemical equations, and general recognition.
- **Streaming Output and Local Preview**: Server responses stream in real-time to the editing area and can be modified. Recognized formula codes can be rendered for preview; the application generates a local temporary HTML file and invokes the KaTeX engine to display it.
- **AI Conversational Correction**: Built-in multi-turn AI conversation capabilities allow users to ask follow-up questions and correct current recognition results, subsequently appending the corrected text to the results area.
- **Automation Capabilities**: Supports features such as auto-recognition after image import, auto-copy after recognition, continuous/batch recognition, and text recognition.
- **History Management**: All recognition results are archived sequentially in the history records. Supports importing and exporting structured record files. Individual records can be loaded, copied, or deleted.
- **API Configuration Management**: Supports custom API endpoints and multi-API management; supports configuration import, reset, and save workflows.

## Interface and Views

The application GUI adopts a split-pane layout (left and right):

**Left Panel (Configuration and Operations)**
- **Configuration Area**: Configure the AI platform (URL/Key/Model) and recognition functions (prompts). Provides network connectivity testing, as well as functions to save, import, and reset configurations.
- **Operations Area**: Provides three buttons ("Screenshot", "Paste", "File") for convenient image input, and a "Start Recognize" button to initiate tasks. Includes checkboxes to toggle modes: Auto recognize, Auto copy, Continuous recognize, and Text recognize.

**Right Panel (Workspace and Feedback)**
- **Recognition Target**: Displays the current pending image. Users can click the area to view a large image preview. Image files can also be dragged and dropped into this area.
- **Recognition Result**: Provides real-time streaming output of code text returned by the model. The area is clickable for direct editing. Provides functions for local web preview and copying.
- **History Records**: Archives successfully recognized code text chronologically. Provides functions for importing and exporting historical data.
- **Operation Logs**: Records system states and informational prompts. Unfolding the collapsible panel reveals detailed execution logs and allows direct textual conversations with the AI via the text input box at the bottom.

**Main Window Screenshot:**

![Main Window](docs/about/main_window.png)

**LaTeX Preview Screenshot:**

![KaTeX Render Preview](docs/about/render.png)

## Dependencies and Startup

**Basic Operating Environment**
- OS: Windows 10/11
- Python: `>= 3.8`

**Core Dependencies**
- PySide6 >= 6.5.0
- openai >= 1.1.0
- httpx >= 0.24.0

**Local Deployment Pipeline**

```bash
git clone https://github.com/River-Du/PeckTeX.git
cd PeckTeX
pip install -r requirements.txt
python main.py
```

## Standard Usage Workflow

1. **Configure API and Functions**:
   - On the first run, go to the `Settings` area on the left. In the `Platform` field, enter or select an API platform (the name is customizable). Enter or confirm the platform's `URL` and corresponding API `Key`, and select or input a supported `Model` (**must be a visual VLM model**).
   - After API configuration, click `API Test` in the upper-right corner of the area to verify the service. If the `Operation Logs` indicate "Service test successful", the configuration is correct.
   - In the `Function` dropdown, select or input a recognition function (e.g., "Formula LaTeX") and fill in or confirm the `Prompt` text below.
   - Click the `Save config` button to write the current settings to the local `config.json` file. Subsequent startups will automatically load these configurations, which can then be selected from the dropdown menus.

2. **Input Image**:
   - Click `Screenshot` (global shortcut `Alt+S`) in the left `Settings` area to initiate a screen capture, then use the mouse to select the target area. Alternatively, images can be inputted via system clipboard `Paste` (global shortcut `Ctrl+V`), `File` import, dragging and dropping into the `Recognition Target` area, loading from the built-in `Image Folder`, or right-clicking the `Recognition Target` area.
   - Once the image is inputted, a preview will be displayed in the `Recognition Target` area. Click the image to view it in full size.

3. **Start Recognition**:
   - After confirming the target image, click `Start Recognize` (global shortcut `Alt+Return`) at the bottom left to initiate the task. The application will send the image and prompt via API to the VLM model for processing, and the results will stream into the `Recognition Result` area.
   - Before clicking `Start Recognize`, you can check the nearby boxes (`Auto recognize`, `Auto copy`, `Continuous recognize`, `Text recognize`) to modify the execution behavior. For example, if `Auto recognize` and `Auto copy` are both checked, loading an image will automatically trigger the recognition request, and upon success, the result will be automatically sent to the system clipboard.

4. **Preview the Recognition Result**:
   - After successfully streaming LaTeX text into the `Recognition Result` text box, click the `Preview` button. This will open a system browser page allowing you to confirm the rendered LaTeX typographic layout.
   - If you need to modify the output or test changes, simply click inside the `Recognition Result` area to edit the text directly.
   - Once confirmed, click the `Copy` button to write the result to the system clipboard.

5. **Manage History Records**:
   - In the `History` area, use the mouse wheel to scroll through all past recognition records. All successful results are automatically recorded chronologically. You can also manually click the `Record` button in the `Recognition Result` area to save the current content.
   - Individual entries can be `Copied`, `Loaded` (into the recognition result area), or `Deleted`. You can also manage the unified history files using the `Import` and `Export` buttons in the upper-right corner of the history area.

6. **View Logs and Chat with AI**:
   - The `Operation Logs` area includes a `Status Bar` indicating system action responses. Click the `Status Bar` to expand the panel and review fully detailed logs, including AI conversation records and system notifications.
   - When the area is expanded, you can communicate directly with the AI via the text input box located at the bottom. Type your input and click `Send`; the AI will respond based on the active conversational context. Provide correct text adjustments by highlighting the text inside the AI's response, right-clicking, and selecting `Append to Result`.

7. **Other Technical Tips**:
   - Every interactive button features hover tooltips. Rest your mouse pointer over any component to read its specific functional instructions.
   - All application parameters (APIs, functions, shortcuts, optional features, etc.) can be directly modified in the `config.json` file. Direct manual edits to this file will take effect upon saving and restarting the application.

## Configuration Parsing

Fundamental operational rules and state variables are preserved inside the `config.json` file generated in the working directory. At each startup, the system validates the contents and reverts unhandled structural faults using a default template.

Primary field descriptions:

- `auto_recognize`: Corresponds to the `Auto recognize` checkbox. When `true`, loading new image sources (via screenshot, pasting, etc.) immediately triggers a background recognition call.
- `auto_copy`: Corresponds to the `Auto copy` checkbox. When `true`, successful recognition outputs are automatically written to the system clipboard.
- `continuous_recognition`: Corresponds to the `Continuous recognize` checkbox. When `true`, clicking Start Recognize will automatically loop request parsing across items inside the built-in image folder sequentially until all images are completed.
- `text_recognition`: Corresponds to the `Text recognize` checkbox. When `true`, clicking Start Recognize will not send an image, but forward the textual content located in the results area along with the prompt to the AI. Suitable for text-based structural requests instead of image matrix tasks.
- `continuous_chat`: When `true`, pressing Start Recognize will not purge the earlier AI contextual dialogue history. Suitable for scenarios requiring multi-turn dialogues for result correction.
- `language`: Reserved field.
- `theme`: Reserved field.
- `image_sort`: Validates the sorting sequence parsing the built-in image directory folder. Accepts `"time"` (by modification date) or `"name"` (by alphabetical filenames).
- `api_timeout`: Determines the duration threshold before network connection requests suspend via timeout errors, mapped in seconds (Range `0.1 - 300`).
- `max_history`: The maximum cap for retaining local history archive records. Entering data items past this point automatically overwrites the oldest components (Range `10-1000`).
- `max_log`: Bounds bottom component message arrays retaining textual line counts pushing oldest strings past capacity out (Range `10-1000`).
- `shortcuts`: Stores bound keyboard shortcut parameters. Includes screenshot (`screenshot`), pasting (`paste`), and launching executions (`recognize`). Expected values must be conforming Qt definitions (e.g., `Ctrl`, `Alt`, `Shift`, `Meta`, `Space`, `Esc`, `Return`, `Tab`, etc.).
- `default`: Points to specific dropdown default configurables populating upon active boot. Encompasses predefined choices targeting `platform`, `model`, and explicit prompt `function`. These values will load into the GUI menu passively at application start.
- `platforms`: Defines configuration structures for different API providers. You can define multiple providers such as `openai` and `siliconflow`. Each provider includes `api_url`, `api_key`, and `models` fields.
- `system_prompt`: Sets the system prompt rules addressing the Large Model behavior characteristics.
- `functions`: Defines structural prompt texts for corresponding tasks. Multiple function definitions like `formula_latex`, `handwriting`, etc. can be specified, providing direct guidance regarding target formatting requirements.

## Project Architecture

The application relies on the `PySide6` component stack, compartmentalized across the following architectural structures:

```text
📁 PeckTeX/
│
├── main.py               # Application entry point
├── config.json           # Configuration file
├── assets/icons/         # Graphic icon resources
├── docs/                 # Documentation resources
│   ├── about/            # Project introduction resources
│   └── examples/         # Example resources
├── src/                  # Application source code
│   ├── gui.py            # Main application UI programming
│   ├── gui_components.py # GUI library components programming
│   ├── theme.py          # Theme distribution logic
│   ├── api_client.py     # API connector parameters
│   ├── renderer.py       # Temporary runtime HTML parsing logic
│   ├── screenshot.py     # Screencap programming rules
│   └── settings.py       # Local file variables parsing
└── userdata/             # User cache
    ├── history/          # Archived active recognition history text
    └── images/           # Built-in image directory files
```

## Frequently Asked Questions (FAQ)

**Q: How do I troubleshoot if recognition fails?**

A: Please ensure your API configuration is correct and passes the `API Test`. If the test fails, expand `Operation Logs` to review the detailed error prompts and attempt the following: 1. Confirm API settings. 2. Check API Key permissions. 3. Switch to another **Vision VLM** model. 4. Verify network connectivity. 5. Retry later. If the `API Test` passes but standard recognition errors out, please check the internal log prompts.

**Q: What should I do if the formula misses subscripts or misidentifies symbols?**

A: Output text can be directly manually modified within the `Recognition Result` text field. Alternately, use the recommended follow-up dialogue sequence: Expand the `Operation Logs` and instruct the model directly using the chat box at the base (e.g., "Please correct the code above, the variable k should be i"). Once returned, highlight the corrected code segment, right-click, and select `Append to Result`.

**Q: How do I call models that are not included in the pre-configured dropdown list?**

A: Direct typing inside the `Model` drop-down functions perfectly. Enter the precise system model ID natively and press enter. Provided the service end complies directly with standard OpenAI protocols, the application will successfully route requests.

**Q: Does it support batch recognition?**

A: Yes. You can click the `Image Folder` button opening the built-in image directory, passing image payloads natively into the folder. With the `Continuous recognize` flag box enabled, hit `Start Recognize`. The core application logic automatically resolves standard consecutive queries through all images consecutively.

**Q: I don’t have an API Key, what should I do?**

A: Simply visit matching provider websites to register an account and retrieve an API Key. Please confirm the Key has sufficient endpoint permissions for calling visual Large Language Models (VLMs). Common aggregating platforms like Siliconflow, OpenRouter, ModelScope, or primary platforms like OpenAI and Zhipu GLM, all provide vision API services. Refer to the respective platform manuals.

**Q: Is it possible to switch the application language?**

A: In the current version, the local application interface is exclusively in Simplified Chinese.

## License

This project is open-sourced under the [MIT License](LICENSE).  
**Copyright (c) 2026 RiverDu**
