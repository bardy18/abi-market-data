"""Build script to create a distributable package of the ABI Trading Platform.

This script uses PyInstaller to create a standalone executable with all dependencies.
It includes empty trades.json and blacklist.json files for user-specific data.
It also embeds S3 credentials for accessing the market data bucket.

Run this script from the packaging/ directory. It will access parent directories as needed.
"""
import os
import sys
import shutil
import json
import base64
from pathlib import Path
from typing import Optional


# Get the parent directory (abi-market-data root)
PROJECT_ROOT = Path(__file__).parent.parent


def embed_s3_credentials():
    """Embed S3 credentials into the s3_config.py file."""
    # Load credentials from s3_config.json - check packaging folder first, then root
    packaging_dir = Path(__file__).parent
    project_root = packaging_dir.parent
    config_paths = [
        packaging_dir / 's3_config.json',  # Preferred location
        project_root / 's3_config.json',  # Fallback location
    ]
    
    config_path = None
    for path in config_paths:
        if path.exists():
            config_path = path
            break
    
    if not config_path:
        print("[!] Warning: s3_config.json not found!")
        print("    The executable will not have embedded S3 credentials.")
        print("    Create s3_config.json in either:")
        print("      - packaging/s3_config.json (preferred)")
        print("      - s3_config.json (project root)")
        print("    Copy packaging/s3_config.json.example as a template.")
        print("    Users will need to provide their own s3_config.json if credentials are not embedded.")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        bucket = config.get('snapshots_bucket')
        region = config.get('region', 'us-east-1')
        access_key = config.get('access_key')
        secret_key = config.get('secret_key')
        
        if not all([bucket, access_key, secret_key]):
            print("[!] Warning: packaging/s3_config.json missing required fields!")
            print("    Required: snapshots_bucket, access_key, secret_key")
            return False
        
        # Obfuscate: base64 encode the credentials
        credential_string = f"{bucket}:{region}:{access_key}:{secret_key}"
        encoded = base64.b64encode(credential_string.encode('utf-8')).decode('utf-8')
        
        # Update the s3_config.py file in trading_app
        default_config_path = PROJECT_ROOT / 'trading_app' / 's3_config.py'
        
        if not default_config_path.exists():
            print("[!] Error: trading_app/s3_config.py not found!")
            return False
        
        # Read current content
        with open(default_config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace the _encoded_config line
        old_line = "    _encoded_config = None"
        new_line = f"    _encoded_config = '{encoded}'"
        
        if old_line not in content:
            print("[!] Warning: Could not find expected line to replace in s3_config.py")
            return False
        
        content = content.replace(old_line, new_line)
        
        # Write back
        with open(default_config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[OK] Embedded S3 credentials for bucket: {bucket}")
        print(f"    Region: {region}")
        print(f"    Note: Credentials are obfuscated but can be extracted by determined reverse engineers")
        print(f"    Use a service account with minimal read-only permissions!")
        
        return True
    except Exception as e:
        print(f"[!] Error embedding credentials: {e}")
        return False


def restore_s3_config_default():
    """Restore s3_config.py to its original state (no embedded credentials)."""
    default_config_path = PROJECT_ROOT / 'trading_app' / 's3_config.py'
    
    if not default_config_path.exists():
        return
    
    try:
        with open(default_config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find and replace back to None
        import re
        pattern = r"_encoded_config = '[^']+'"
        replacement = "_encoded_config = None"
        
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            
            with open(default_config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("[OK] Restored s3_config.py to original state")
    except Exception as e:
        print(f"[!] Warning: Could not restore s3_config.py: {e}")


def create_empty_json_files(output_dir: Path):
    """Create empty trades.json and blacklist.json files."""
    trades_file = output_dir / 'trades.json'
    blacklist_file = output_dir / 'blacklist.json'
    
    # Create empty trades list
    with open(trades_file, 'w', encoding='utf-8') as f:
        json.dump([], f, indent=2, ensure_ascii=False)
    
    # Create empty blacklist
    with open(blacklist_file, 'w', encoding='utf-8') as f:
        json.dump({'items': []}, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] Created {trades_file.name}")
    print(f"[OK] Created {blacklist_file.name}")


def create_pyinstaller_spec():
    """Create a PyInstaller spec file for the trading app."""
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    [r'{PROJECT_ROOT / "trading_app" / "main.py"}'],
    pathex=[],
    binaries=[],
    datas=[
        (r'{PROJECT_ROOT / "trading_app" / "config.yaml"}', 'trading_app'),
        (r'{PROJECT_ROOT / "mappings" / "display_mappings.json"}', 'mappings'),
        (r'{PROJECT_ROOT / "mappings" / "ocr_mappings.json"}', 'mappings'),
        (r'{PROJECT_ROOT / "trading_app" / "icon.ico"}', 'trading_app'),
    ],
    hiddenimports=[
        'PySide6',
        'matplotlib',
        'pandas',
        'numpy',
        'yaml',
        'boto3',
        'botocore',
        'trading_app.s3_config',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ABI_Trading_Platform',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI application, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'{PROJECT_ROOT / "trading_app" / "icon.ico"}',
)
'''
    
    # Store spec file in packaging folder to avoid cluttering root
    packaging_dir = Path(__file__).parent
    spec_path = packaging_dir / 'ABI_Trading_Platform.spec'
    with open(spec_path, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"[OK] Created {spec_path.name} in packaging folder")
    return spec_path


def build_executable():
    """Build the executable using PyInstaller."""
    import subprocess
    
    spec_path = create_pyinstaller_spec()
    
    print("\n[*] Building executable with PyInstaller...")
    print("    This may take several minutes...\n")
    
    try:
        # Change to project root for PyInstaller (PyInstaller needs to run from project root)
        original_cwd = os.getcwd()
        os.chdir(PROJECT_ROOT)
        
        try:
            # Use absolute path to spec file since we're running from project root
            result = subprocess.run(
                [sys.executable, '-m', 'PyInstaller', '--clean', str(spec_path)],
                check=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)
            if result.stderr:
                print("Warnings:", result.stderr)
            return True
        finally:
            os.chdir(original_cwd)
    except subprocess.CalledProcessError as e:
        print(f"[!] Build failed: {e}")
        print(e.stdout)
        print(e.stderr)
        return False
    except FileNotFoundError:
        print("[!] PyInstaller not found. Install it with:")
        print("    pip install pyinstaller")
        return False


def get_download_config():
    """Get download bucket configuration from s3_config.json."""
    packaging_dir = Path(__file__).parent
    project_root = packaging_dir.parent
    config_paths = [
        packaging_dir / 's3_config.json',  # Preferred location
        project_root / 's3_config.json',  # Fallback location
    ]
    
    download_bucket = None
    region = 'us-east-1'
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    download_bucket = config.get('download_bucket')
                    region = config.get('region', 'us-east-1')
                    
                    if download_bucket:
                        return download_bucket, region
            except Exception:
                continue
    
    # Default fallback
    return 'abi-market-data-downloads', region


def upload_package_to_s3(zip_path: Path) -> Optional[str]:
    """Upload the ZIP package to S3 for public download.
    
    Returns the public download URL if successful, None otherwise.
    """
    import subprocess
    
    if not zip_path.exists():
        print("[!] ZIP file not found for upload")
        return None
    
    print("\n[*] Uploading package to S3...")
    
    # Get download configuration
    download_bucket, region = get_download_config()
    
    # Build S3 key
    s3_key = "ABI_Trading_Platform.zip"
    s3_path = f"s3://{download_bucket}/{s3_key}"
    
    print(f"    Bucket: {download_bucket}")
    print(f"    S3 Path: {s3_path}")
    
    try:
        # Upload to S3 (bucket policy handles public access, no ACL needed)
        result = subprocess.run(
            ['aws', 's3', 'cp', str(zip_path), s3_path, '--profile', 'abi'],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Build public URL
        if region == 'us-east-1':
            download_url = f"https://{download_bucket}.s3.amazonaws.com/{s3_key}"
        else:
            download_url = f"https://{download_bucket}.s3.{region}.amazonaws.com/{s3_key}"
        
        print(f"[OK] Upload completed successfully!")
        print(f"    Download URL: {download_url}")
        return download_url
        
    except subprocess.CalledProcessError as e:
        print(f"[!] Upload failed: {e}")
        print("    Please check:")
        print("      - AWS CLI is installed: aws --version")
        print("      - AWS credentials are configured: aws configure list")
        print("      - Bucket name is correct and exists")
        print("      - You have write permissions to the bucket")
        print("      - Bucket policy allows public read access")
        return None
    except FileNotFoundError:
        print("[!] AWS CLI not found. Install it to enable automatic upload.")
        print("    Install AWS CLI: https://aws.amazon.com/cli/")
        return None


def create_package():
    """Create the final distributable package."""
    dist_dir = PROJECT_ROOT / 'dist'
    build_dir = PROJECT_ROOT / 'build'
    exe_file = dist_dir / 'ABI_Trading_Platform.exe'
    output_dir = dist_dir / 'ABI_Trading_Platform'
    
    # Check if executable exists
    if not exe_file.exists():
        print("[!] Executable not found: dist/ABI_Trading_Platform.exe")
        print("    Build may have failed.")
        return False
    
    # Create output directory for package
    output_dir.mkdir(exist_ok=True)
    
    # Copy executable to package directory
    import shutil
    package_exe = output_dir / 'ABI_Trading_Platform.exe'
    shutil.copy2(exe_file, package_exe)
    print(f"[OK] Copied executable to package directory")
    
    # Create empty JSON files
    create_empty_json_files(output_dir)
    
    # Create a README for the package
    readme_content = """ABI Trading Platform - Standalone Package

INSTALLATION:
1. Extract this folder to any location on your computer
2. Create a shortcut to ABI_Trading_Platform.exe
3. Place the shortcut on your desktop or Start menu

FILES:
- ABI_Trading_Platform.exe: The main application
- trades.json: Your personal trade tracking (starts empty)
- blacklist.json: Items you want to hide (starts empty)

USAGE:
- Double-click ABI_Trading_Platform.exe to launch
- The app will automatically download market data snapshots
- Your trades.json and blacklist.json will be saved in this folder
- You can move these files if needed, but keep them with the .exe
"""
    
    readme_path = output_dir / 'README.txt'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"\n[OK] Package created in {output_dir}")
    
    # Create ZIP file for distribution
    print("\n[*] Creating ZIP file for distribution...")
    zip_path = dist_dir / 'ABI_Trading_Platform.zip'
    
    try:
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all files from the package directory
            for file_path in output_dir.rglob('*'):
                if file_path.is_file():
                    # Get relative path from output_dir
                    arcname = file_path.relative_to(output_dir)
                    zipf.write(file_path, arcname)
                    print(f"    Added: {arcname}")
        
        zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"\n[OK] ZIP file created: {zip_path.name} ({zip_size_mb:.1f} MB)")
        
        # Clean up temporary files: remove the package directory and standalone exe
        print("\n[*] Cleaning up temporary files...")
        try:
            if output_dir.exists():
                shutil.rmtree(output_dir)
                print(f"[OK] Removed {output_dir.name} directory")
            
            if exe_file.exists():
                exe_file.unlink()
                print(f"[OK] Removed standalone {exe_file.name}")
        except Exception as e:
            print(f"[!] Warning: Could not clean up temporary files: {e}")
        
        return zip_path
    except Exception as e:
        print(f"[!] Error creating ZIP file: {e}")
        print("    Package is still available in the directory, but ZIP creation failed")
        return None


def main():
    """Main build process."""
    print("="*60)
    print("ABI Trading Platform - Package Builder")
    print("="*60)
    print()
    
    # Check if we're in the right location (packaging/ directory)
    if not (PROJECT_ROOT / 'trading_app').exists():
        print("[!] Error: trading_app directory not found!")
        print("    Run this script from the packaging/ directory.")
        return 1
    
    # Embed S3 credentials
    print("\n[*] Embedding S3 credentials...")
    credentials_embedded = embed_s3_credentials()
    
    if not credentials_embedded:
        print("\n[!] Continuing without embedded credentials.")
        print("    Users will need to provide s3_config.json in the project root")
        print("    or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
    
    download_url = None
    try:
        # Build executable
        if not build_executable():
            return 1
        
        # Create package
        zip_path = create_package()
        if not zip_path:
            return 1
        
        # Upload to S3
        download_url = upload_package_to_s3(zip_path)
        
        # Clean up dist folder after successful upload
        if download_url:
            print("\n[*] Cleaning up dist folder...")
            dist_dir = PROJECT_ROOT / 'dist'
            try:
                if zip_path.exists():
                    zip_path.unlink()
                    print(f"[OK] Removed {zip_path.name}")
                if dist_dir.exists() and not any(dist_dir.iterdir()):
                    dist_dir.rmdir()
                    print(f"[OK] Removed empty dist folder")
                elif dist_dir.exists():
                    # Check if there are any remaining files
                    remaining = list(dist_dir.iterdir())
                    if remaining:
                        print(f"[*] Note: {len(remaining)} file(s) remain in dist folder")
            except Exception as e:
                print(f"[!] Warning: Could not clean up dist folder: {e}")
        
        # Clean up build folder
        print("\n[*] Cleaning up build folder...")
        build_dir = PROJECT_ROOT / 'build'
        if build_dir.exists():
            try:
                shutil.rmtree(build_dir)
                print(f"[OK] Removed build folder")
            except Exception as e:
                print(f"[!] Warning: Could not remove build folder: {e}")
    finally:
        # Always restore the original file (remove embedded credentials from source)
        print("\n[*] Restoring source files...")
        restore_s3_config_default()
    
    print("\n" + "="*60)
    print("Build complete!")
    print("="*60)
    
    if download_url:
        print(f"\n[OK] Package uploaded successfully!")
        print(f"    Download URL: {download_url}")
        print("\nNext steps:")
        print("1. Update DOWNLOAD_URL in website/script.js with the URL above (if not already set)")
        print("2. Deploy updated website")
    else:
        print("\n[!] Package built but not uploaded to S3")
        print("    Upload will be retried automatically on next build")
        print("\nNext steps:")
        print("1. Fix any upload issues (check AWS CLI, credentials, bucket permissions)")
        print("2. Re-run build script to upload")
        print("3. Update DOWNLOAD_URL in website/script.js with the S3 URL")
        print("4. Deploy updated website")
    
    if credentials_embedded:
        print("\n[!] SECURITY REMINDER:")
        print("    - Embedded credentials are obfuscated but can be extracted")
        print("    - Use a service account with READ-ONLY permissions")
        print("    - Consider rotating credentials periodically")
        print("    - Monitor S3 access logs for suspicious activity")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

