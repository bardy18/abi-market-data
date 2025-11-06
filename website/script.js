// Smooth scroll and download button handler

// ============================================================
// CONFIGURATION: S3 download URL
// ============================================================
const DOWNLOAD_URL = 'https://abi-market-data-downloads.s3.us-east-1.amazonaws.com/ABI_Trading_Platform.zip';

document.addEventListener('DOMContentLoaded', function() {
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Screenshot image handler - show placeholder if image doesn't exist
    const screenshotImg = document.getElementById('app-screenshot');
    const screenshotPlaceholder = document.getElementById('screenshot-placeholder');
    
    if (screenshotImg && screenshotPlaceholder) {
        screenshotImg.addEventListener('error', function() {
            // Image failed to load, show placeholder
            screenshotImg.style.display = 'none';
            screenshotPlaceholder.classList.add('show');
        });
        
        screenshotImg.addEventListener('load', function() {
            // Image loaded successfully, hide placeholder
            screenshotPlaceholder.classList.remove('show');
        });
        
        // Check if src is empty or invalid
        if (!screenshotImg.src || screenshotImg.src.endsWith('app-screenshot.png')) {
            // Try to load the image, will trigger error handler if it doesn't exist
            const img = new Image();
            img.onerror = function() {
                screenshotImg.style.display = 'none';
                screenshotPlaceholder.classList.add('show');
            };
            img.onload = function() {
                screenshotPlaceholder.classList.remove('show');
            };
            img.src = screenshotImg.src;
        }
    }

    // Download button handler
    const downloadBtn = document.getElementById('download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function(e) {
            if (DOWNLOAD_URL) {
                // Redirect to S3 download URL
                window.location.href = DOWNLOAD_URL;
                console.log('Download initiated:', DOWNLOAD_URL);
            } else {
                // Show alert if URL not configured
                e.preventDefault();
                alert('Download link not configured.\n\nTo set up:\n1. Build the package: scripts\\build_package.bat\n   (Upload to S3 happens automatically)\n2. Update DOWNLOAD_URL in website/script.js with the URL from build output');
            }
        });
        
        // Update href if DOWNLOAD_URL is set
        if (DOWNLOAD_URL) {
            downloadBtn.href = DOWNLOAD_URL;
        }
    }

    // Add fade-in animation on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe all sections
    document.querySelectorAll('section').forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(20px)';
        section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(section);
    });
});

