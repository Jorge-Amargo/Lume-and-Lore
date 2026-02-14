// --- GLOBAL STATE ---
let story;
let currentProject = "";
let unlockedImages = { scenes: [], rewards: [] };
let activeGalleryTab = 'scenes';

// UI References
const storyContainer = document.querySelector('#story-text');
const choicesContainer = document.querySelector('#choices-container');
const imageElement = document.querySelector('#scene-image');
const rewardBanner = document.querySelector('#reward-banner');

// --- INITIALIZATION ---
window.onload = () => {
    loadManifest();
};

function loadManifest() {
    checkResumeStatus();
    const selector = document.getElementById('project-selector');
    const manifestPath = '../data/output/manifest.json';
    console.log(`[DEBUG] Loading manifest from: ${manifestPath}`);

    fetch(manifestPath)
        .then(response => {
            if (!response.ok) throw new Error(`Manifest not found (HTTP ${response.status}). Run dashboard.py first.`);
            return response.json();
        })
        .then(projects => {
            selector.innerHTML = ""; // Clear "Loading..."
            
            // Populate Dropdown
            projects.forEach(proj => {
                let opt = document.createElement('option');
                opt.value = proj.id;
                opt.innerText = proj.title;
                selector.appendChild(opt);
            });
            
            // Select first option & check for save
            if (projects.length > 0) {
                selector.value = projects[0].id;
                checkResumeStatus();
            }
            
            // Update save status when user changes selection
            selector.onchange = checkResumeStatus;
        })
        .catch(err => {
            console.error(err);
            selector.innerHTML = "<option>Error loading games</option>";
        });
}

function checkResumeStatus() {
    const selector = document.getElementById('project-selector');
    if (!selector || !selector.value) return;
    
    const projectId = selector.value;
    const saveKey = `save_state_${projectId}`;
    const hasSave = localStorage.getItem(saveKey);

    // Look for an existing resume button or create one
    let resumeBtn = document.getElementById('resume-btn');
    
    // We append it to the main menu area
    const menuArea = document.querySelector('#main-menu .menu-buttons') || document.getElementById('main-menu');

    if (hasSave) {
        if (!resumeBtn) {
            resumeBtn = document.createElement('button');
            resumeBtn.id = 'resume-btn';
            resumeBtn.className = 'menu-btn primary'; 
            resumeBtn.innerText = "Resume Journey";
            resumeBtn.style.marginTop = "10px";
            
            resumeBtn.onclick = () => {
                const savedData = localStorage.getItem(saveKey);
                startGame(savedData);
            };
            
            // Insert it after the "Start New Journey" button if possible
            if (menuArea) menuArea.appendChild(resumeBtn);
        }
        resumeBtn.style.display = 'block';
    } else {
        if (resumeBtn) resumeBtn.style.display = 'none';
    }
}

// --- GAME ENGINE ---
function startGame(saveData = null) {
    currentProject = document.getElementById('project-selector').value;
    const assetsBase = `/data/output/${currentProject}/assets/`;
    console.log(`[DEBUG] Assets Base set to: ${assetsBase}`);
    if (!currentProject) {
        alert("Please select an adventure from the list first.");
        return;
    }
    // 1. Load Gallery Progress
    const storedArt = localStorage.getItem(`unlocked_art_${currentProject}`);
    if (storedArt) unlockedImages = JSON.parse(storedArt);
    if (storyContainer) storyContainer.innerHTML = "";
    document.getElementById('main-menu').style.display = 'none';
    const statusBar = document.getElementById('status-bar');
    if (statusBar) statusBar.style.display = 'none';
    document.getElementById('game-container').style.display = 'grid';

    if (imageElement) {
        imageElement.src = "";
        imageElement.style.opacity = 0;
    }
    
    fetch(`${assetsBase}../adventure.json`)
        .then(r => r.json())
        .then(json => {
            if (typeof inkjs === 'undefined') {
                alert("CRITICAL ERROR: 'ink.js' not found.");
                return;
            }
            
            try {
                story = new inkjs.Story(json);
                
                // UI Cleanup
                const mainMenu = document.getElementById('main-menu');
                const statusBar = document.getElementById('status-bar');
                if (mainMenu) mainMenu.style.display = 'none';
                if (statusBar) statusBar.style.display = 'none';
                document.getElementById('game-container').style.display = 'grid';

                // LOGIC FIX: Load save data if provided (e.g. from file upload)
                if (saveData) {
                    console.log("[DEBUG] Restoring save state...");
                    story.state.LoadJson(saveData);
                }

                continueStory(); 
            } catch (e) {
                console.error("Story Init Error:", e);
            }
        })
        .catch(e => console.error("Could not load adventure.json", e));
}

// --- FILE I/O FUNCTIONS ---

function handleFileUpload(input) {
    const file = input.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        const jsonContent = e.target.result;
        startGame(jsonContent);
    };
    reader.readAsText(file);
}

function downloadSaveFile() {
    if (!story) return;
    const saveState = story.state.ToJson();
    const blob = new Blob([saveState], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentProject}_save_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function continueStory() {
    if (!story) return;
    choicesContainer.innerHTML = "";
    
    // START CREATE: Enhanced main loop to ensure scrolling works
    while (story.canContinue) {
        const text = story.Continue();
        const paragraph = document.createElement('p');
        paragraph.innerText = text;
        
        // Highlight logic for outcome text is handled in renderChoices now
        
        storyContainer.appendChild(paragraph);
        handleTags(story.currentTags);
    }
    // STOP DELETE: [Previous simple loop]

    renderChoices();
    
    // START CREATE: Improved scrolling
    requestAnimationFrame(() => {
        const textPane = document.getElementById('text-container');
        if (textPane) {
            // instant scroll for small updates, smooth for large chunks
            textPane.scrollTo({
                top: textPane.scrollHeight,
                behavior: 'smooth'
            });
        }
    });
    // STOP DELETE: [Previous simple scroll]
}

function renderChoices() {
    choicesContainer.innerHTML = ""; 

    /* START CREATE: Improved Flow. 
       Old logic stopped after one line. New logic continues story automatically 
       to prevent getting stuck between paragraphs. 
    */
    story.currentChoices.forEach(choice => {
        const button = document.createElement('button');
        button.innerText = choice.text;
        button.className = "choice-btn"; 
        
        button.onclick = () => {
            story.ChooseChoiceIndex(choice.index);
            const saveState = story.state.ToJson();
            localStorage.setItem(`save_state_${currentProject}`, saveState);
            choicesContainer.innerHTML = "";

            // Check if there is content to show immediately
            if (story.canContinue) {
                // We manually pull the first line to apply the 'outcome-text' styling
                const outcomeText = story.Continue();
                const p = document.createElement('p');
                p.innerText = outcomeText;
                p.className = "outcome-text"; 
                storyContainer.appendChild(p);
                handleTags(story.currentTags);

                // Now continue the rest of the scene normally
                continueStory();
            } else {
                // Corner case: End of story
                renderContinueButton("End of Story. Restart?");
            }
        };
        choicesContainer.appendChild(button);
    });
    /* STOP DELETE: [Old click handler that created "Next Scene" buttons for every paragraph] */
}

function renderPacingButton() {
    let btn = document.createElement('button');
    btn.innerText = "Continue...";
    btn.classList.add('choice-btn');
    btn.style.borderColor = "#666";
    btn.onclick = () => {
        btn.remove();
        continueStory();
    };
    choicesContainer.appendChild(btn);
}

function renderContinueButton(label) {
    choicesContainer.innerHTML = "";
    const nextBtn = document.createElement('button');
    nextBtn.className = "choice-btn";
    nextBtn.style.gridColumn = "1 / span 3"; 
    nextBtn.innerText = label;
    
    nextBtn.onclick = () => {
        if (label.includes("lost your way") || label.includes("End")) {
            location.reload(); 
        } else {
            storyContainer.innerHTML = "";
            continueStory();
        }
    };
    choicesContainer.appendChild(nextBtn);
}

// --- ASSET & TAG HANDLING ---
function handleTags(tags) {
    if (!tags || tags.length === 0) return;
    
    tags.forEach(tag => {
        if (tag.startsWith("IMAGE:")) {
            const fileName = tag.split(":")[1].trim();
            const fullPath = `/data/output/${currentProject}/assets/${fileName}`;
            
            if (imageElement) {
                // Preload image to prevent "pop-in"
                const tempImg = new Image();
                tempImg.src = fullPath;
                tempImg.onload = () => {
                    imageElement.style.opacity = 0; // Fade out old (start transition)
                    
                    // Wait for CSS fade-out (300ms), then swap source and fade in
                    setTimeout(() => {
                        imageElement.src = fullPath;
                        imageElement.style.opacity = 1; 
                    }, 300);

                    // Optional: Scroll text if needed (kept from your code)
                    requestAnimationFrame(() => {
                        const textPane = document.getElementById('text-container');
                        if (textPane) {
                            textPane.scrollTo({
                                top: textPane.scrollHeight,
                                behavior: 'smooth'
                            });
                        }
                    });
                };
            }

            const isReward = fileName.includes("_reward");
            const type = isReward ? "rewards" : "scenes";

            if (!unlockedImages[type].includes(fileName)) {
                unlockedImages[type].push(fileName);
                localStorage.setItem(`unlocked_art_${currentProject}`, JSON.stringify(unlockedImages));
            }

            if (isReward) {
                imageElement.classList.add("reward-pulse");
                rewardBanner.style.display = "block";
            } else {
                imageElement.classList.remove("reward-pulse");
                rewardBanner.style.display = "none";
            }
        } 
    });
}
           
// --- GALLERY LOGIC ---
function toggleGallery(show) {
    document.getElementById('gallery-overlay').style.display = show ? 'flex' : 'none';
    if (show) {
        currentProject = document.getElementById('project-selector').value;
        const assetsBase = `/data/output/assets/${currentProject}/`;
        const storedArt = localStorage.getItem(`unlocked_art_${currentProject}`);
        unlockedImages = storedArt ? JSON.parse(storedArt) : { scenes: [], rewards: [] };
        renderGallery();
    }
}

function switchTab(tab) {
    activeGalleryTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('active');
        if (b.innerText.toLowerCase().includes(tab)) b.classList.add('active');
    });
    renderGallery();
}

function renderGallery() {
    const grid = document.getElementById('gallery-grid');
    grid.innerHTML = "";
    
    const images = unlockedImages[activeGalleryTab] || [];
    
    if (images.length === 0) {
        grid.innerHTML = `<p style="color:#666; width:100%;">No ${activeGalleryTab} unlocked yet.</p>`;
        return;
    }

    images.forEach(fileName => {
        const img = document.createElement('img');
        img.src = `/data/output/${currentProject}/assets/${fileName}`;
        img.className = "gallery-thumb";
        img.title = fileName;
        grid.appendChild(img);
    });
}