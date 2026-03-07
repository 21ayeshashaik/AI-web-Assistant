// Function injected into the webpage to extract ONLY the main content
function scrapeWebpageText() {
    let clone = document.body.cloneNode(true);
    const junkTags = ['nav', 'aside', 'footer', 'header', 'script', 'style', 'noscript', 'iframe', 'svg', 'form', 'button'];
    junkTags.forEach(tag => {
        let elements = clone.querySelectorAll(tag);
        elements.forEach(el => el.remove());
    });
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
    let mainContent = clone.querySelector('article') || clone.querySelector('main');
    if (!mainContent) {
        let paragraphs = clone.querySelectorAll('p');
        let maxScore = 0;
        let bestContainer = clone;
        paragraphs.forEach(p => {
            let textLen = p.innerText.trim().length;
            if (textLen < 30) return;
            let parent = p.parentElement;
            parent.score = (parent.score || 0) + textLen;
            if (parent.score > maxScore) {
                maxScore = parent.score;
                bestContainer = parent;
            }
        });
        mainContent = bestContainer.parentElement || bestContainer;
    }
    let goodElements = mainContent.querySelectorAll('p, h1, h2, h3, h4, li');
    let fullText = Array.from(goodElements)
        .map(el => el.innerText.trim())
        .filter(text => text.length > 30)
        .join('\n\n');
    if (fullText.length < 150) {
        fullText = mainContent.innerText.trim();
    }
    return fullText;
}

// Main logic to process the AI request
async function processWithAI(taskName) {
    const resultDiv = document.getElementById('result');
    const loader = document.getElementById('loader');
    const quizContainer = document.getElementById('quiz-container');
    const flashcardContainer = document.getElementById('flashcard-container');

    // Reset Views
    resultDiv.innerText = "";
    loader.style.display = "block";
    if (quizContainer) quizContainer.style.display = "none";
    if (flashcardContainer) flashcardContainer.style.display = "none";

    // Hide result box for structured tasks
    if (taskName === 'mcq' || taskName === 'flashcards') {
        resultDiv.style.display = "none";
    } else {
        resultDiv.style.display = "block";
    }

    try {
        let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        let injectionResults = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: scrapeWebpageText,
        });

        let pageText = injectionResults[0].result;
        if (!pageText || pageText.length < 50) {
            loader.style.display = "none";
            resultDiv.style.display = "block";
            resultDiv.innerText = "Error: Could not find the main article text on this website.";
            return;
        }

        const response = await fetch('http://127.0.0.1:5000/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: pageText, task: taskName })
        });

        const data = await response.json();
        loader.style.display = "none";

        if (data.items && data.items.length > 0) {
            if (taskName === 'mcq') {
                quizContainer.style.display = "flex";
                quizContainer.innerHTML = "";
                data.items.forEach((mcq, index) => {
                    const block = document.createElement('div');
                    block.className = 'mcq-block';
                    const question = document.createElement('p');
                    question.className = 'mcq-question';
                    question.innerText = `${index + 1}. ${mcq.question}`;
                    block.appendChild(question);
                    const feedback = document.createElement('span');
                    feedback.className = 'mcq-feedback';
                    const optionsContainer = document.createElement('div');
                    const optionButtons = [];
                    const shuffledOptions = [...mcq.options].sort(() => Math.random() - 0.5);
                    shuffledOptions.forEach((opt) => {
                        const btn = document.createElement('button');
                        btn.className = 'mcq-option';
                        btn.innerText = opt;
                        btn.addEventListener('click', () => {
                            optionButtons.forEach(b => b.disabled = true);
                            if (opt === mcq.answer) {
                                btn.classList.add('correct');
                                feedback.innerText = "\u2714 Correct!";
                                feedback.classList.add('correct');
                            } else {
                                btn.classList.add('wrong');
                                feedback.innerText = "\u2718 Incorrect";
                                feedback.classList.add('wrong');
                                const correctBtn = optionButtons.find(b => b.innerText === mcq.answer);
                                if (correctBtn) correctBtn.classList.add('correct');
                            }
                        });
                        optionButtons.push(btn);
                        optionsContainer.appendChild(btn);
                    });
                    block.appendChild(optionsContainer);
                    block.appendChild(feedback);
                    quizContainer.appendChild(block);
                });
            } else if (taskName === 'flashcards') {
                flashcardContainer.style.display = "flex";
                flashcardContainer.innerHTML = "";
                data.items.forEach(item => {
                    const card = document.createElement('div');
                    card.className = 'flashcard';
                    card.innerHTML = `
                        <div class="flashcard-inner">
                            <div class="flashcard-front">
                                ${item.question}
                                <div class="flashcard-hint">Tap to See Answer</div>
                            </div>
                            <div class="flashcard-back">
                                ${item.answer}
                                <div class="flashcard-hint">Tap to See Question</div>
                            </div>
                        </div>
                    `;
                    card.addEventListener('click', () => card.classList.toggle('flipped'));
                    flashcardContainer.appendChild(card);
                });
            }
        } else if (data.result) {
            resultDiv.style.display = "block";
            resultDiv.innerHTML = "";
            const heading = document.createElement("h3");
            heading.style.marginTop = "0";
            heading.style.marginBottom = "12px";
            heading.style.color = "#111827";
            heading.style.fontSize = "18px";
            heading.style.fontWeight = "700";
            heading.innerText = taskName === "summarize" ? "Web Summary" : "Generated Output";

            const contentBody = document.createElement("div");
            contentBody.innerText = data.result;
            resultDiv.appendChild(heading);
            resultDiv.appendChild(contentBody);
        } else {
            resultDiv.style.display = "block";
            resultDiv.innerText = "Error: " + (data.error || "Could not process request");
        }
    } catch (error) {
        loader.style.display = "none";
        resultDiv.style.display = "block";
        resultDiv.innerText = "Connection Failed! Make sure your Python app.py server is running.";
        console.error(error);
    }
}

// Initialize Popup
document.addEventListener('DOMContentLoaded', () => {
    let currentTask = "summarize";
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentTask = e.target.getAttribute('data-task');

            const generateBtn = document.getElementById('btn-generate');
            const resultDiv = document.getElementById('result');
            const quizContainer = document.getElementById('quiz-container');
            const flashcardContainer = document.getElementById('flashcard-container');

            if (currentTask === 'summarize') {
                if (generateBtn) generateBtn.innerText = "Generate Web Summary";
                if (resultDiv) resultDiv.style.display = "block";
                if (quizContainer) quizContainer.style.display = "none";
                if (flashcardContainer) flashcardContainer.style.display = "none";
            } else if (currentTask === 'flashcards') {
                if (generateBtn) generateBtn.innerText = "Generate Flashcards";
                if (resultDiv) resultDiv.style.display = "none";
                if (quizContainer) quizContainer.style.display = "none";
                if (flashcardContainer) flashcardContainer.style.display = "none";
            } else {
                if (generateBtn) generateBtn.innerText = "Generate Quiz";
                if (resultDiv) resultDiv.style.display = "none";
                if (quizContainer) quizContainer.style.display = "none";
                if (flashcardContainer) flashcardContainer.style.display = "none";
            }
            if (resultDiv) resultDiv.innerText = "Click a button above to scan this webpage.";
        });
    });

    const genBtn = document.getElementById('btn-generate');
    if (genBtn) {
        genBtn.addEventListener('click', () => {
            processWithAI(currentTask);
        });
    }

    const closeBtn = document.getElementById('btn-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            if (window !== window.parent) {
                window.parent.postMessage({ action: "closeAIWidget" }, "*");
            } else {
                window.close();
            }
        });
    }
});