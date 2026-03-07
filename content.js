// Create the floating button
const fab = document.createElement('div');
fab.id = "ai-web-assistant-fab";
fab.innerHTML = "🤖";
Object.assign(fab.style, {
    position: 'fixed',
    bottom: '20px',
    right: '60px',
    width: '60px',
    height: '60px',
    borderRadius: '50%',
    backgroundColor: '#3b82f6',
    color: 'white',
    fontSize: '32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    boxShadow: '0 4px 14px rgba(0,0,0,0.25)',
    zIndex: '2147483646',
    transition: 'transform 0.2s, background-color 0.2s',
    userSelect: 'none'
});

// Hover effects
fab.addEventListener('mouseover', () => { fab.style.transform = 'scale(1.08)'; });
fab.addEventListener('mouseout', () => { fab.style.transform = 'scale(1)'; });

// Create the iframe container
const iframeContainer = document.createElement('div');
iframeContainer.id = "ai-web-assistant-iframe-container";
Object.assign(iframeContainer.style, {
    position: 'fixed',
    top: '20px',
    right: '20px',
    width: '500px',
    maxWidth: 'calc(100vw - 40px)',
    height: '700px',
    maxHeight: 'calc(100vh - 40px)',
    backgroundColor: 'transparent',
    zIndex: '2147483647',
    display: 'none',
    overflow: 'visible'
});

// Create the iframe
const iframe = document.createElement('iframe');
iframe.src = chrome.runtime.getURL('popup.html');
iframe.setAttribute('frameborder', '0');
Object.assign(iframe.style, {
    width: '100%',
    height: '100%',
    border: 'none !important',
    backgroundColor: 'transparent'
});

iframeContainer.appendChild(iframe);
document.body.appendChild(fab);
document.body.appendChild(iframeContainer);

// Toggle functionality
let isOpen = false;
fab.addEventListener('click', () => {
    isOpen = !isOpen;
    if (isOpen) {
        iframeContainer.style.display = 'block';
        fab.innerHTML = "&#10006;"; // Close Icon
        fab.style.backgroundColor = '#ef4444'; // Red when open
    } else {
        iframeContainer.style.display = 'none';
        fab.innerHTML = "🤖";      // Robot Icon
        fab.style.backgroundColor = '#3b82f6'; // Blue when closed
    }
});

// Listen for close events coming from inside the React/Extension iframe
window.addEventListener("message", (event) => {
    if (event.data.action === "closeAIWidget") {
        isOpen = false;
        iframeContainer.style.display = 'none';
        fab.innerHTML = "🤖";
        fab.style.backgroundColor = '#3b82f6';
    }
});
