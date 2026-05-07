#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIMP DDS Export Plugin using texconv

Provides a complete DDS export workflow with progress feedback, comprehensive logging,
and support for various DDS compression formats.

Author: Tenir
Version: 2.0
GIMP Compatibility: 3.0+
"""

import sys
import gi
import subprocess
import os
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from contextlib import contextmanager

gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')
gi.require_version('Gtk', '3.0')

from gi.repository import Gimp, GimpUi, Gtk, GLib, GObject, Gio

# Configure logging
LOG_DIR = Path.home() / '.gimp-3.0'
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / 'dds_export.log'

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@dataclass
class DDSExportOptions:
    """Data class for DDS export configuration."""
    format: str
    mipmap: bool
    srgb: bool
    overwrite: bool


def get_texconv_path() -> str:
    """
    Resolve texconv executable path.
    
    Checks in this order:
    1. TEXCONV_PATH environment variable
    2. System PATH (via 'where' on Windows or 'which' on Unix)
    3. Common installation locations
    
    Returns:
        str: Path to texconv executable
        
    Raises:
        FileNotFoundError: If texconv cannot be found
    """
    logger.debug("Resolving texconv path...")
    
    # Check environment variable
    env_path = os.getenv('TEXCONV_PATH')
    if env_path and os.path.isfile(env_path):
        logger.info(f"Found texconv via TEXCONV_PATH: {env_path}")
        return env_path
    
    # Try to find in system PATH
    try:
        result = subprocess.run(
            ['where', 'texconv.exe'] if sys.platform == 'win32' else ['which', 'texconv'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            texconv_path = result.stdout.strip().split('\n')[0]
            logger.info(f"Found texconv in system PATH: {texconv_path}")
            return texconv_path
    except Exception as e:
        logger.debug(f"System PATH search failed: {e}")
    
    # Common installation locations for Windows
    if sys.platform == 'win32':
        common_paths = [
            "C:/Program Files/texconv/texconv.exe",
            "C:/Program Files (x86)/texconv/texconv.exe",
            "C:/tools/texconv.exe",
            os.path.expanduser("~/texconv/texconv.exe")
        ]
        for path in common_paths:
            if os.path.isfile(path):
                logger.info(f"Found texconv at common location: {path}")
                return path
    
    error_msg = (
        "texconv.exe not found. Please install it or set TEXCONV_PATH environment variable. "
        "Download from: https://github.com/microsoft/DirectXTex/releases"
    )
    logger.error(error_msg)
    raise FileNotFoundError(error_msg)


def validate_image(image: Gimp.Image) -> None:
    """
    Validate image before export.
    
    Args:
        image: GIMP image object
        
    Raises:
        ValueError: If image fails validation
    """
    logger.debug(f"Validating image: {image.get_name()}")
    
    width = image.get_width()
    height = image.get_height()
    
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image dimensions: {width}x{height}")
    
    # DDS textures should typically be power of 2 or multiples of 4
    if (width % 4 != 0) or (height % 4 != 0):
        logger.warning(
            f"Image dimensions ({width}x{height}) are not multiples of 4. "
            "DDS compression may produce suboptimal results."
        )
    
    logger.info(f"Image validation passed: {width}x{height}")


def validate_export_path(export_path: str) -> None:
    """
    Validate export path before attempting conversion.
    
    Args:
        export_path: Target DDS file path
        
    Raises:
        ValueError: If path is invalid or not writable
    """
    logger.debug(f"Validating export path: {export_path}")
    
    output_dir = os.path.dirname(export_path)
    
    if not output_dir:
        raise ValueError("Export path must include directory")
    
    if not os.path.isdir(output_dir):
        raise ValueError(f"Output directory does not exist: {output_dir}")
    
    if not os.access(output_dir, os.W_OK):
        raise ValueError(f"Output directory is not writable: {output_dir}")
    
    # Check if file exists and is writable
    if os.path.isfile(export_path) and not os.access(export_path, os.W_OK):
        raise ValueError(f"Target file is not writable: {export_path}")
    
    logger.info(f"Export path validation passed: {export_path}")


def build_texconv_command(
    texconv_path: str,
    format_name: str,
    options: DDSExportOptions,
    temp_png: str,
    output_dir: str
) -> List[str]:
    """
    Build texconv command with all appropriate flags.
    
    Args:
        texconv_path: Path to texconv executable
        format_name: DDS format (e.g., "BC1_UNORM")
        options: Export options
        temp_png: Path to temporary PNG file
        output_dir: Output directory
        
    Returns:
        List[str]: Complete command to execute
    """
    logger.debug(f"Building texconv command for format: {format_name}")
    
    command = [
        texconv_path,
        "-f", format_name,
        "-o", output_dir,
        "-ft", "DDS",
        temp_png
    ]
    
    # Add optional flags
    if options.overwrite:
        command.insert(2, "-y")
    
    if options.mipmap:
        command.extend(["-m", "0"])  # Generate all mip levels
    
    if options.srgb:
        command.append("-srgb")
    
    logger.debug(f"Built command: {' '.join(command)}")
    return command


@contextmanager
def temp_png_file():
    """
    Context manager for temporary PNG file with guaranteed cleanup.
    
    Yields:
        str: Path to temporary PNG file
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    temp_path = temp_file.name
    temp_file.close()
    
    logger.debug(f"Created temporary file: {temp_path}")
    
    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.debug(f"Cleaned up temporary file: {temp_path}")
            except OSError as e:
                logger.warning(f"Failed to remove temporary file {temp_path}: {e}")


def save_temp_image(image: Gimp.Image, filepath: str) -> None:
    """
    Export image as temporary PNG.
    
    Args:
        image: GIMP image object
        filepath: Target PNG file path
        
    Raises:
        RuntimeError: If PNG export fails
    """
    logger.debug(f"Saving temporary PNG: {filepath}")
    
    try:
        png_proc = Gimp.get_pdb().lookup_procedure("file-png-export")
        config = png_proc.create_config()
        config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
        config.set_property("image", image)
        config.set_property("file", Gio.File.new_for_path(filepath))
        
        result = png_proc.run(config)
        
        if result.index(0) != Gimp.PDBStatusType.SUCCESS:
            error_msg = "Unknown error"
            if len(result) > 1 and result.index(1):
                error_msg = result.index(1).message
            raise RuntimeError(f"PNG export failed: {error_msg}")
        
        logger.info(f"Successfully saved temporary PNG: {filepath}")
        
    except Exception as e:
        logger.error(f"Temporary PNG save error: {e}", exc_info=True)
        raise RuntimeError(f"Failed to save temporary image: {e}")


def run_texconv(command: List[str]) -> str:
    """
    Execute texconv with the given command.
    
    Args:
        command: Command list to execute
        
    Returns:
        str: texconv stdout output
        
    Raises:
        RuntimeError: If texconv execution fails
    """
    logger.debug(f"Executing texconv: {' '.join(command)}")
    
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            timeout=300  # 5 minute timeout
        )
        logger.info("texconv execution completed successfully")
        return result.stdout
        
    except subprocess.TimeoutExpired:
        error_msg = "texconv execution timed out (5 minutes)"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
        
    except subprocess.CalledProcessError as e:
        error_msg = f"texconv failed with exit code {e.returncode}: {e.stderr}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
        
    except Exception as e:
        logger.error(f"texconv execution error: {e}", exc_info=True)
        raise RuntimeError(f"Failed to execute texconv: {e}")


def finalize_export(output_dir: str, temp_png: str, export_path: str) -> None:
    """
    Finalize export by moving texconv output to target location.
    
    Args:
        output_dir: Directory where texconv created the DDS file
        temp_png: Path to temporary PNG (used to determine texconv output name)
        export_path: Final DDS file path
        
    Raises:
        FileNotFoundError: If texconv output file not found
        OSError: If file move operation fails
    """
    logger.debug("Finalizing export...")
    
    # texconv creates output with same base name as input but .DDS extension
    temp_base = os.path.splitext(os.path.basename(temp_png))[0]
    texconv_output = os.path.join(output_dir, f"{temp_base}.DDS")
    
    logger.debug(f"Looking for texconv output: {texconv_output}")
    
    if not os.path.isfile(texconv_output):
        raise FileNotFoundError(
            f"texconv did not produce output file at: {texconv_output}. "
            "Check texconv compatibility and command-line arguments."
        )
    
    try:
        os.replace(texconv_output, export_path)
        logger.info(f"Successfully moved DDS file to: {export_path}")
    except OSError as e:
        logger.error(f"Failed to finalize export: {e}", exc_info=True)
        raise


class DDSExportPlugin(Gimp.PlugIn):
    """Main GIMP plugin for DDS export using texconv."""
    
    def __init__(self):
        """Initialize plugin with format mappings."""
        super().__init__()
        self.format_map: Dict[str, str] = {
            "BC1 / DXT1": "BC1_UNORM",
            "BC2 / DXT3": "BC2_UNORM",
            "BC3 / DXT5": "BC3_UNORM",
            "BC4 (R)": "BC4_UNORM",
            "BC5 (RG)": "BC5_UNORM",
            "BC7 (HQ)": "BC7_UNORM",
            "R8G8B8A8 (Uncompressed)": "R8G8B8A8_UNORM"
        }
        logger.info("DDS Export Plugin initialized")

    def do_query_procedures(self) -> List[str]:
        """Return list of procedure names."""
        return ["jb-dds-export"]

    def do_set_i18n(self, name: str) -> bool:
        """Set internationalization (disabled for now)."""
        return False

    def do_create_procedure(self, name: str) -> Gimp.ImageProcedure:
        """Create and configure the export procedure."""
        procedure = Gimp.ImageProcedure.new(
            self, name,
            Gimp.PDBProcType.PLUGIN,
            self.run, None
        )
        procedure.set_image_types("*")
        procedure.set_menu_label("Export as DDS (texconv)...")
        procedure.add_menu_path("<Image>/File/Export")
        procedure.set_documentation(
            "Export to DDS using texconv",
            "Exports the image to DDS using the external tool texconv with support for "
            "BC1-BC7 compression, mipmap generation, and sRGB color space.",
            name
        )
        procedure.set_attribution("Tenir", "Tenir", "2025")
        return procedure

    def show_export_dialog(self) -> Optional[DDSExportOptions]:
        """
        Display DDS export options dialog.
        
        Returns:
            DDSExportOptions: Selected options, or None if canceled
        """
        logger.debug("Showing export dialog")
        
        GimpUi.init("dds-export")

        dialog = Gtk.Dialog(title="Export image as DDS (texconv)", flags=0)
        dialog.set_default_size(400, 250)
        dialog.set_border_width(10)

        content = dialog.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        content.add(grid)

        # Format selection
        format_label = Gtk.Label(label="Compression format:", xalign=0)
        format_combo = Gtk.ComboBoxText()
        for name in self.format_map.keys():
            format_combo.append_text(name)
        format_combo.set_active(0)
        grid.attach(format_label, 0, 0, 1, 1)
        grid.attach(format_combo, 1, 0, 2, 1)

        # Options
        options_label = Gtk.Label(label="Options:", xalign=0)
        mipmap_check = Gtk.CheckButton(label="Generate mipmaps")
        mipmap_check.set_active(True)
        srgb_check = Gtk.CheckButton(label="sRGB color space (perceptual)")
        srgb_check.set_active(True)
        overwrite_check = Gtk.CheckButton(label="Overwrite existing file")
        overwrite_check.set_active(True)

        options_grid = Gtk.Grid(column_spacing=10, row_spacing=5)
        options_grid.attach(mipmap_check, 0, 0, 1, 1)
        options_grid.attach(srgb_check, 0, 1, 1, 1)
        options_grid.attach(overwrite_check, 0, 2, 1, 1)

        grid.attach(options_label, 0, 1, 1, 1)
        grid.attach(options_grid, 1, 1, 2, 1)

        # Info label
        info_label = Gtk.Label(
            label="Log file: ~/.gimp-3.0/dds_export.log",
            xalign=0
        )
        info_label.set_markup(
            "<small><i>Details logged to: ~/.gimp-3.0/dds_export.log</i></small>"
        )
        grid.attach(info_label, 0, 2, 3, 1)

        # Buttons
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Export", Gtk.ResponseType.OK)
        dialog.show_all()

        result = dialog.run()
        options = None
        
        if result == Gtk.ResponseType.OK:
            selected_format = format_combo.get_active_text()
            options = DDSExportOptions(
                format=self.format_map.get(selected_format, "BC1_UNORM"),
                mipmap=mipmap_check.get_active(),
                srgb=srgb_check.get_active(),
                overwrite=overwrite_check.get_active()
            )
            logger.info(f"Export options selected: {options}")
        else:
            logger.info("Export dialog canceled")
        
        dialog.destroy()
        return options

    def run(
        self,
        procedure: Gimp.ImageProcedure,
        run_mode: Gimp.RunMode,
        image: Gimp.Image,
        drawables: Any,
        config: Any,
        run_data: Any
    ) -> Gimp.ValueArray:
        """
        Main export procedure.
        
        Args:
            procedure: GIMP procedure object
            run_mode: Execution mode
            image: GIMP image object
            drawables: Image drawables
            config: Procedure configuration
            run_data: Additional runtime data
            
        Returns:
            Gimp.ValueArray: Procedure return values
        """
        logger.info("="*60)
        logger.info("DDS Export procedure started")
        logger.info(f"Image: {image.get_name()}, Mode: {run_mode}")
        
        if run_mode != Gimp.RunMode.INTERACTIVE:
            logger.info("Non-interactive mode not supported")
            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

        try:
            # Progress: 5%
            Gimp.progress_init("Preparing DDS export...")
            Gimp.progress_update(0.05)
            
            # Get export options
            logger.info("Step 1/10: Showing export dialog")
            options = self.show_export_dialog()
            if not options:
                logger.info("Export canceled by user")
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            
            # Progress: 15%
            Gimp.progress_update(0.15)
            
            # Get file path
            logger.info("Step 2/10: Showing file chooser")
            file_chooser = Gtk.FileChooserDialog(
                title="Save as DDS",
                action=Gtk.FileChooserAction.SAVE,
                buttons=("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.OK)
            )
            file_chooser.set_current_name("texture.dds")

            filter_dds = Gtk.FileFilter()
            filter_dds.set_name("DDS files")
            filter_dds.add_pattern("*.dds")
            file_chooser.add_filter(filter_dds)

            response = file_chooser.run()
            export_path = None
            if response == Gtk.ResponseType.OK:
                export_path = file_chooser.get_filename()
                if export_path and not export_path.lower().endswith(".dds"):
                    export_path += ".dds"
            file_chooser.destroy()

            if not export_path:
                logger.info("File selection canceled by user")
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            
            logger.info(f"Export path selected: {export_path}")
            
            # Progress: 20%
            Gimp.progress_update(0.20)

            # Validate image
            logger.info("Step 3/10: Validating image")
            validate_image(image)
            
            # Progress: 25%
            Gimp.progress_update(0.25)
            
            # Validate export path
            logger.info("Step 4/10: Validating export path")
            validate_export_path(export_path)
            
            # Progress: 30%
            Gimp.progress_update(0.30)
            
            # Resolve texconv path
            logger.info("Step 5/10: Locating texconv")
            texconv_path = get_texconv_path()
            
            # Progress: 40%
            Gimp.progress_update(0.40)

            # Create temporary PNG and export image
            with temp_png_file() as temp_png:
                logger.info("Step 6/10: Exporting image to temporary PNG")
                Gimp.progress_update(0.45)
                save_temp_image(image, temp_png)
                
                # Progress: 50%
                Gimp.progress_update(0.50)
                
                # Build and execute texconv command
                logger.info("Step 7/10: Building texconv command")
                output_dir = os.path.dirname(export_path)
                command = build_texconv_command(
                    texconv_path,
                    options.format,
                    options,
                    temp_png,
                    output_dir
                )
                
                # Progress: 60%
                Gimp.progress_update(0.60)
                
                logger.info("Step 8/10: Executing texconv")
                Gimp.progress_update_text("Converting to DDS...")
                output_text = run_texconv(command)
                
                # Progress: 80%
                Gimp.progress_update(0.80)
                
                # Finalize export
                logger.info("Step 9/10: Finalizing export")
                finalize_export(output_dir, temp_png, export_path)

            # Progress: 95%
            Gimp.progress_update(0.95)
            
            logger.info("Step 10/10: Export complete")
            logger.info("="*60)
            
            # Progress: 100%
            Gimp.progress_update(1.0)
            
            # Show success message
            success_msg = (
                f"Successfully exported to:\n{export_path}\n\n"
                f"Format: {options.format}\n"
                f"Mipmaps: {'Yes' if options.mipmap else 'No'}\n"
                f"sRGB: {'Yes' if options.srgb else 'No'}\n\n"
                f"Check ~/.gimp-3.0/dds_export.log for details."
            )
            Gimp.message(success_msg)
            logger.info(f"Success message: {success_msg}")

            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

        except Exception as e:
            error_msg = f"DDS Export Error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            Gimp.message(f"{error_msg}\n\nCheck ~/.gimp-3.0/dds_export.log for details.")
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error.new_literal(GLib.quark_from_string("DDS Export"), str(e), -1)
            )


if __name__ == "__main__":
    logger.info("Starting GIMP DDS Export Plugin")
    Gimp.main(DDSExportPlugin.__gtype__, sys.argv)
