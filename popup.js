// Function injected into the webpage to extract ONLY the main content
function scrapeWebpageText() {
    // 1. Clone the body so we don't accidentally delete the visual website for the user
    let clone = document.body.cloneNode(true);

    // 2. Aggressively remove HTML tags we KNOW are junk
    const junkTags =['nav', 'aside', 'footer', 'header', 'script', 'style', 'noscript', 'iframe', 'svg', 'form', 'button'];
    junkTags.forEach(tag => {
        let elements = clone.querySelectorAll(tag);
        elements.forEach(el => el.remove());
    });

    // 3. Wildcard Deletion: Remove anything with classes/IDs that sound like junk
    // The *= means "contains". This catches "right-sidebar", "ad-banner-top", etc.
    const junkSelectors = [
        '[class*="sidebar"]', '[id*="sidebar"]',
        '[class*="ad-"]', '[id*="ad-"]', '[class*="ads"]', '[class*="advert"]',
        '[class*="comment"]', '[id*="comment"]',
        '[class*="menu"]', '[id*="menu"]',
        '[class*="popup"]', '[class*="cookie"]', '[class*="nav"]'
    ];
    junkSelectors.forEach(selector => {
        let elements = clone.querySelectorAll(selector);
        elements.forEach(el => el.remove());
    });

    // 4. Try to find the Main Container
    let mainContent = clone.querySelector('article') || clone.querySelector('main');
    
    // 5. TEXT DENSITY SCORING (If no <article> tag is found)
    // We look for the container that holds the most paragraph text.
    if (!mainContent) {
        let paragraphs = clone.querySelectorAll('p');
        let maxScore = 0;
        let bestContainer = clone; // Default to whole body

        paragraphs.forEach(p => {
            let textLen = p.innerText.trim().length;
            if (textLen < 30) return; // Skip tiny texts
            
            let parent = p.parentElement;
            // Give the parent a score based on how much text it holds
            parent.score = (parent.score || 0) + textLen;
            
            if (parent.score > maxScore) {
                maxScore = parent.score;
                bestContainer = parent;
            }
        });
        
        // Go up one level to capture headers related to those paragraphs
        mainContent = bestContainer.parentElement || bestContainer;
    }

    // 6. Extract the structured text (Paragraphs, Headers, Lists)
    let goodElements = mainContent.querySelectorAll('p, h1, h2, h3, h4, li');
    let fullText = Array.from(goodElements)
        .map(el => el.innerText.trim())
        .filter(text => text.length > 30) // Ignore single words like "Share" or "Like"
        .join('\n\n');

    // 7. Fallback: If structured extraction failed, just grab the raw text of the cleaned container
    if (fullText.length < 150) {
        fullText = mainContent.innerText.trim();
    }

    return fullText;
}

// Main logic to process the AI request
async function processWithAI(taskName) {
    const resultDiv = document.getElementById('result');
    const loader = document.getElementById('loader');
    
    resultDiv.innerText = "";
    loader.style.display = "block";

    try {
        let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        // Execute our ultra-robust scraper
        let injectionResults = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: scrapeWebpageText,
        });

        let pageText = injectionResults[0].result;

        // Failsafe check
        if (!pageText || pageText.length < 50) {
            loader.style.display = "none";
            resultDiv.innerText = "Error: Could not find the main article text on this website. It might be an image-only page or highly restricted.";
            return;
        }

        // Send to your Python Backend
        const response = await fetch('http://127.0.0.1:5000/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                text: pageText, 
                task: taskName 
            })
        });

        const data = await response.json();
        loader.style.display = "none";

        if (data.result) {
            resultDiv.innerText = data.result;
        } else {
            resultDiv.innerText = "Error: " + data.error;
        }

    } catch (error) {
        loader.style.display = "none";
        resultDiv.innerText = "Connection Failed! Make sure your Python app.py server is running in your terminal.";
        console.error(error);
    }
}

// Attach clicking events to the three buttons
document.getElementById('btn-sum').addEventListener('click', () => processWithAI('summarize'));
document.getElementById('btn-flash').addEventListener('click', () => processWithAI('flashcards'));
document.getElementById('btn-mcq').addEventListener('click', () => processWithAI('mcq'));