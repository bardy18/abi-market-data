# ABI Trading Platform Website

## Overview

This is the official website for the ABI Trading Platform. It serves two main purposes:

1. **For Traders**: Download the trading platform and learn about features
2. **For Tencent**: A clear message about the project's compliance and vision

## Files

- `index.html` - Main website page
- `styles.css` - Styling and layout
- `script.js` - Interactive features and smooth scrolling

## Deployment

### Option 1: Static Hosting (Recommended)

Upload all files to any static hosting service:
- GitHub Pages
- Netlify
- Vercel
- AWS S3 + CloudFront
- Any web hosting service

Simply upload the `website/` folder contents to your hosting provider.

### Option 2: Simple HTTP Server

For local testing:
```bash
cd website
python -m http.server 8000
```

Then visit `http://localhost:8000`

## Customization

### Update Download Link

The download link is configured in `script.js` using the `DOWNLOAD_URL` constant:

1. **Build the package**:
   ```bash
   scripts\build_package.bat
   ```

2. **Upload to S3**:
   Upload happens automatically during the build process. The download URL will be displayed in the build output.

3. **Update `script.js`**:
   ```javascript
   const DOWNLOAD_URL = 'https://your-bucket.s3.region.amazonaws.com/path/ABI_Trading_Platform.zip';
   ```

The upload script uses:
- Separate download bucket (configure `download_bucket` in `s3_config.json`)
- Default bucket: `abi-market-data-downloads` (if not configured)

### Update Community Links

In `index.html`, update the community links section with your actual Reddit, Discord, and GitHub URLs.

### S3 Configuration Note

For building the executable with embedded S3 credentials:

1. **Create S3 Configuration**:
   - Copy `packaging/s3_config.json.example` to `packaging/s3_config.json`
   - Fill in your S3 bucket name, region, and IAM service account credentials
   - The build script will embed these credentials into the executable

2. **For Distribution**:
   - Use a private S3 bucket with a service account (IAM user)
   - Give the service account read-only permissions
   - Credentials are obfuscated in the executable but can be extracted by determined reverse engineers
   - Consider rotating credentials periodically

## Design

The website uses a modern dark theme with:
- Neon green (`#00ff88`) and orange (`#ff6600`) accents
- Dark background for a gaming/trading aesthetic
- Responsive design for mobile and desktop
- Smooth animations and transitions

## Message to Tencent

The website includes a dedicated section explaining:
- The project is a hobby project
- Full compliance with game policies
- Manual data collection process
- Invitation for partnership/acquisition

This section is clearly visible and emphasizes respect for Tencent's policies and the desire to work together officially.

