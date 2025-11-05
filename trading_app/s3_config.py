"""Default S3 configuration embedded in the executable.

This file contains default S3 credentials for accessing the market data bucket.
These credentials are obfuscated and embedded at build time.

SECURITY NOTE: While obfuscated, determined reverse engineers could potentially
extract these credentials. We use a service account with minimal read-only
permissions to limit potential damage.
"""

import base64


def get_default_s3_config():
    """Get default S3 configuration with obfuscated credentials.
    
    Returns None if no default config is available (for local development).
    """
    # Obfuscated credentials (base64 encoded)
    # In production build, these will be set by the build script
    # Format: base64(bucket:region:access_key:secret_key)
    
    # This will be replaced during build with actual credentials
    # For now, return None to allow local development without embedded creds
    _encoded_config = None
    
    if _encoded_config is None:
        return None
    
    try:
        # Decode the obfuscated config
        decoded = base64.b64decode(_encoded_config).decode('utf-8')
        parts = decoded.split(':')
        
        if len(parts) != 4:
            return None
        
        return {
            'bucket': parts[0],
            'region': parts[1],
            'access_key': parts[2],
            'secret_key': parts[3],
            'use_s3': True,
            'key_prefix': 'snapshots/',
        }
    except Exception:
        return None

