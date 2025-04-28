# LivephotoConverter

A powerful utility for backing up, converting, and managing Live Photos from Apple devices.

![LivePhoto Backup Tool](./logo.png)

## Features

- **Live Photo Support**: Process standard Live Photos (image+video pairs)
- **LIVP Format**: Extract and process .livp format files
- Multiple Output Formats:
  - Original format preservation
  - MP4 conversion
  - GIF conversion
  - Static JPG extraction
- **Image Format Support**: Process HEIC, JPG, PNG and other common image formats
- **Directory Structure**: Option to preserve original folder structure
- Performance Optimized:
  - Multi-threaded processing
  - Optional GPU acceleration (when available)
- User-Friendly Interface:
  - Folder structure browser
  - File preview functionality
  - Real-time processing logs

## Installation

### Standalone Executable

Download the latest release from the [Releases](https://github.com/afovo/LivephotoConverter/releases) page.

The application is packaged as a single executable with all dependencies included - no installation needed.

### Building from Source

#### Prerequisites

- Python 3.6+

- FFmpeg (included in the dependencies folder)

- Required Python packages:

  ```
  pip install pillow tkinterpip install pillow-heif  # Optional, for better HEIC support
  ```

#### Steps

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/livephoto-backup-tool.git
   cd livephoto-backup-tool
   ```

2. Run the application:

   ```
   python main.py
   ```

3. Build a standalone executable:

   ```
   pip install pyinstaller
   pyinstaller --onefile --windowed --icon=icon.ico --add-data "dependencies;dependencies" main.py
   ```

   The executable will be available in the `dist` folder.

## Usage

1. **Select Input Directory**: Choose the folder containing your Live Photos
2. **Select Output Directory**: Choose where processed files will be saved
3. Configure Options:
   - Select output format for Live Photos
   - Choose whether to preserve folder structure
   - Enable/disable LIVP file preservation
   - Set performance parameters (thread count, GPU acceleration)
4. **Start Processing**: Click the "Start Processing" button to begin
5. **Monitor Progress**: View real-time logs and progress in the main window

## File Format Support

### Input Formats

- Live Photo pairs (JPG/HEIC + MOV)
- LIVP container files
- Standard image files (JPG, PNG, GIF, BMP, TIFF, HEIC)

### Output Formats

- MP4 (recommended for most users)
- GIF (for web compatibility)
- JPG (static image only)
- Original format preservation

## Technical Details

The application uses FFmpeg for media processing, with these key components:

- **FFmpeg**: Handles video conversion and HEIC processing
- **Tkinter**: Provides the graphical user interface
- **PIL/Pillow**: Manages image processing tasks
- **Pillow-HEIF**: Optional component for improved HEIC file support

## Troubleshooting

- **FFmpeg Missing**: The application requires FFmpeg for video processing. If not detected, only basic image functionality will be available.
- **HEIC Support**: For full HEIC support, the pillow-heif package is recommended.
- **Performance Issues**: Reduce thread count on lower-end systems or disable GPU acceleration if experiencing problems.

## License

Copyright © 2025 All rights reserved.

## Acknowledgements

- FFmpeg for media processing capabilities
- PIL/Pillow for image processing
- The Python community for various libraries and tools