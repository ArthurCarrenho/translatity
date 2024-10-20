# Translatity

Translatity is a powerful and user-friendly application that allows you to translate subtitle files (SRT format) using Google's Gemini AI model. It provides a graphical user interface for easy file management, translation settings, and progress tracking.

![Translatity Screenshot](https://i.imgur.com/t5SuoyJ.png)

## Motivation

This project was born out of a desire to leverage the impressive capabilities of Google's Gemini 1.5 Pro model, particularly its expansive 2M token context window, to deliver superior, context-aware machine translations. The goal is to provide a free and accessible tool for anyone in supported regions to benefit from this cutting-edge technology.

## Features

- Translate SRT files from one language to another
- Support for multiple API keys with automatic rotation (W.I.P.)
- Drag-and-drop file addition to the translation queue
- File preview functionality
- Progress tracking for individual files and the entire queue
- Contextual translation to maintain tone and style
- Settings persistence for convenience

## Demo

Here's an non-cherrypicked non-normalized example result of an entire season of subtitles translated for english to portuguese using this method:

https://github.com/ArthurCarrenho/DegrassiTngSubs/tree/pt/S01

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/ArthurCarrenho/translatity.git
   cd translatity
   ```

2. Install the required dependencies:
   ```
   pip install PyQt6 google-generativeai
   ```

   **Note:** The `google-generativeai` package currently has known compatibility issues with Python 3.13. Please consider using an alternative Python version if you encounter problems.

3. Set up your Google API key(s):
   - Obtain API key(s) from the [Google AI Studio](https://aistudio.google.com/app/apikey)
   - You can add your API keys directly in the application

## Usage

1. Run the application:
   ```
   python main.py
   ```

2. Add your Google API key(s) in the application interface.

3. Select SRT files for translation by clicking the "Select SRT File(s)" button or dragging and dropping files into the application window.

4. Choose the source and target languages from the dropdown menus.

5. (Optional) Provide context for the translation in the text box.

6. Click the "Translate Queue" button to start the translation process.

7. Monitor the progress in the status bar and progress indicator.

8. Access translated files in the same directory as the original files, with "output_" prefix.

## Project Structure

- `main.py`: Entry point of the application
- `gui/`
  - `main_window.py`: Main application window and logic
  - `widgets.py`: Custom widget definitions
  - `themes.py`: Theme-related functions
- `translation/`
  - `translator.py`: Core translation logic using Google's Gemini AI

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the GNU General Public License v3.0 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Google Gemini AI for powering the translations
- PyQt6 for the graphical user interface

## Disclaimer

This tool uses Google's Gemini AI model for translations. While it strives for accuracy, machine translations may not always be perfect. It's recommended to review and edit the translated subtitles for critical content.