// --- GLOBAL STATE ---
let story;
let currentProject = "";
let unlockedImages = { scenes: [], rewards: [] };
let activeGalleryTab = 'scenes';
let typewriterEnabled = true;
let typewriterSpeed = 50; // milliseconds per character

// UI References
const storyContainer = document.querySelector('#story-text');
const choicesContainer = document.querySelector('#choices-container');
const imageElement = document.querySelector('#scene-image');
const rewardBanner = document.querySelector('#reward-banner');

// --- INITIALIZATION ---
window.onload = () => {
    // Restore typewriter setting from localStorage
    const saved = localStorage.getItem('typewriter_enabled');
    if (saved !== null) {
        typewriterEnabled = saved === 'true';
    }
    
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
    
    // Initialize audio manager
    audioManager.init();
    
    // 1. Load Gallery Progress
    const storedArt = localStorage.getItem(`unlocked_art_${currentProject}`);
    if (storedArt) unlockedImages = JSON.parse(storedArt);
    if (storyContainer) storyContainer.innerHTML = "";

    // Aggressively hide overlays and menu (remove overlay class to prevent z-index/backdrop issues)
    const mainMenu = document.getElementById('main-menu');
    if (mainMenu) {
        mainMenu.style.display = 'none';
        mainMenu.classList.remove('overlay');
        mainMenu.setAttribute('aria-hidden', 'true');
        mainMenu.style.zIndex = '0';
    }
    const gallery = document.getElementById('gallery-overlay');
    if (gallery) { gallery.style.display = 'none'; gallery.classList.remove('overlay'); }

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
    
    // We do NOT clear the storyContainer here because 
    // the first line of the scene was already added by the Proceed button
    
    while (story.canContinue) {
        const text = story.Continue();
        const tags = story.currentTags;
        
        const paragraph = document.createElement('p');
        if (tags && tags.length > 0) paragraph.setAttribute('data-tags', tags.join('|'));
        storyContainer.appendChild(paragraph);
        
        // Apply typewriter effect if enabled, otherwise show text instantly
        if (typewriterEnabled) {
            typewriterEffect(text, paragraph, typewriterSpeed);
        } else {
            paragraph.innerText = text;
        }
        
        handleTags(tags);
    }
    
    renderChoices();

    // If no text was produced immediately, defer a check to allow typewriter to start.
    setTimeout(() => {
        const paras = storyContainer.querySelectorAll('p');
        const hasNonEmpty = Array.from(paras).some(p => p.innerText && p.innerText.trim() !== '');
        // If no paragraphs exist, check whether the ink engine actually has text available to push
        if (!hasNonEmpty && paras.length === 0 && story.currentChoices && story.currentChoices.length > 0) {
            if (story.currentText && story.currentText.trim().length > 0) {
                const p = document.createElement('p');
                if (typewriterEnabled) typewriterEffect(story.currentText, p, typewriterSpeed);
                else p.innerText = story.currentText;
                if (story.currentTags && story.currentTags.length > 0) p.setAttribute('data-tags', (story.currentTags || []).join('|'));
                storyContainer.appendChild(p);
                if (story.currentTags && story.currentTags.length > 0) handleTags(story.currentTags);
                renderChoices();
                return;
            }
        }
    }, 300);
    
    // Auto-scroll to top for the new scene
    requestAnimationFrame(() => {
        const textPane = document.getElementById('text-container');
        if (textPane) textPane.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// --- TYPEWRITER EFFECT ---
function typewriterEffect(text, element, speed = 50) {
    let index = 0;
    element.innerText = "";
    
    const type = () => {
        if (index < text.length) {
            element.innerText += text[index++];
            setTimeout(type, speed);
        }
    };
    type();
}

function toggleTypewriter() {
    typewriterEnabled = !typewriterEnabled;
    const btn = document.getElementById('typewriter-toggle');
    if (btn) {
        btn.innerText = typewriterEnabled ? "⌨️ Typewriter ON" : "⌨️ Typewriter OFF";
    }
    localStorage.setItem('typewriter_enabled', typewriterEnabled);
}

function renderChoices() {
    choicesContainer.innerHTML = "";

    story.currentChoices.forEach(choice => {
        const button = document.createElement('button');
        button.innerText = choice.text;
        button.className = "choice-btn";
        if (choice.tags && choice.tags.length > 0) button.setAttribute('data-tags', (choice.tags || []).join('|'));
        
        // --- FIX 1: Detect Button Type BEFORE clicking ---
        // We check the tags on the choice itself, and fallback to the text
        let isBad = false;
        let isExquisite = false;
        
        // Check Ink Tags (if available)
        const cTags = (choice.tags || []).map(t => t.toLowerCase());
        if (cTags.some(t => t.includes('bad') || t.includes('death'))) isBad = true;
        if (cTags.some(t => t.includes('exquisite') || t.includes('reward'))) isExquisite = true;
        
        // Fallback: Check Choice Text (Keywords)
        const lowerText = choice.text.toLowerCase();
        if (lowerText.includes('bad')) isBad = true;
        if (lowerText.includes('exquisite')) isExquisite = true;

        button.onclick = () => {
            // 1. Commit Choice
            story.ChooseChoiceIndex(choice.index);
            // React to choice-level tags immediately (e.g., SFX on choice)
            if (choice.tags && choice.tags.length > 0) handleTags(choice.tags);
            let nextSceneBuffer = null;
            const outcomeFragment = document.createDocumentFragment();

            // 3. Process Outcome Text
            while (story.canContinue) {
                const text = story.Continue();
                const tags = story.currentTags || [];

                // --- FIX 3: Aggressive Text Filter ---
                // Ignores case to ensure "Fate Frowns" is always removed
                if (text.toLowerCase().includes("fate frowns")) {
                    continue; 
                }

                // --- FIX 2: Detect Scene Transition ---
                if (isSceneTransition(tags)) {
                    // STOP! We hit the Next Scene. Save it for the button click.
                    // If the chunk is empty (e.g. IMAGE tag appears before the narration text),
                    // attempt to pull the next chunk from the story so we capture the first paragraph.
                    if (text.trim().length === 0 && story.canContinue) {

                        const nextChunk = story.Continue();
                        const nextTags = story.currentTags || [];

                        // Prefer the pulled chunk as the first narration if it's non-empty
                        const effectiveText = (nextChunk && nextChunk.trim().length > 0) ? nextChunk : text;
                        nextSceneBuffer = { text: effectiveText, tags: (tags || []).concat(nextTags) };
                    } else {
                        nextSceneBuffer = { text, tags };
                    }

                    break; 
                } else {
                    // Render Outcome Text
                    if (text.trim().length > 0) {
                        const p = document.createElement('p');
                        p.innerText = text;
                        p.className = "outcome-text";
                        if (tags && tags.length > 0) p.setAttribute('data-tags', tags.join('|'));
                        outcomeFragment.appendChild(p);
                    }
                    handleTags(tags); 
                }
            }

            // 4. Create "Proceed" Button
            let btnText = "Proceed to next scene";
            if (isExquisite) btnText = "Excellent choice - proceed to next scene";
            if (isBad) btnText = "Your fate is unknown to the author - choose another outcome";

            const proceedBtn = document.createElement('button');
            proceedBtn.className = "choice-btn primary";
            proceedBtn.innerText = btnText;
            proceedBtn.style.width = "100%";
            proceedBtn.style.marginTop = "2rem";
            
            if (isExquisite) {
                proceedBtn.style.borderColor = "gold";
                proceedBtn.style.color = "gold";
            }
            if (isBad) {
                proceedBtn.style.borderColor = "red";
                proceedBtn.style.color = "#ff6b6b";
            }
            // Propagate the originating choice's tags to the proceed button
            if (choice.tags && choice.tags.length > 0) proceedBtn.setAttribute('data-choice-tags', (choice.tags || []).join('|'));

            proceedBtn.onclick = () => {
                // --- FIX 2: Only clear screen if we have a NEW scene ---
                if (nextSceneBuffer) {

                    storyContainer.innerHTML = ""; 
                    
                    // Render the first line of the new scene (if any)
                    if (nextSceneBuffer.text && nextSceneBuffer.text.trim().length > 0) {
                        const p = document.createElement('p');
                        p.innerText = nextSceneBuffer.text;
                        storyContainer.appendChild(p);

                    } else {

                    }
                    handleTags(nextSceneBuffer.tags); 
                }
                // If nextSceneBuffer is null, we just continue (showing choices below the current text)

                continueStory();
            };

            // 5. If we captured a scene transition but the fragment contains the first paragraph
            // move it into nextSceneBuffer so it is shown after the Proceed button (not accidentally cleared).
            if (nextSceneBuffer && (!nextSceneBuffer.text || nextSceneBuffer.text.trim().length === 0)) {
                const lastNode = outcomeFragment.lastChild;
                if (lastNode && lastNode.tagName && lastNode.tagName.toLowerCase() === 'p') {
                    const lastText = lastNode.innerText || '';
                    if (lastText.trim().length > 0) {
                        // Move tags if present on the moved paragraph
                        const movedTags = lastNode.getAttribute('data-tags');
                        nextSceneBuffer.text = lastText;
                        if (movedTags) {
                            const movedArr = (movedTags || '').split('|').filter(Boolean);
                            nextSceneBuffer.tags = (nextSceneBuffer.tags || []).concat(movedArr);
                        }
                        outcomeFragment.removeChild(lastNode);
                    }
                }
            }

            // 6. Append Outcome & Button
            storyContainer.appendChild(outcomeFragment);
            choicesContainer.appendChild(proceedBtn);

            // Scroll to bottom
            requestAnimationFrame(() => {
                const textPane = document.getElementById('text-container');
                if (textPane) textPane.scrollTo({ top: textPane.scrollHeight, behavior: 'smooth' });
            });
        };
        choicesContainer.appendChild(button);
    });
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
const audioManager = {
    currentTrack: null,
    audioElement: null,
    
    init() {
        this.audioElement = new Audio();
        this.audioElement.loop = true;
        this.audioElement.volume = 0.6;
    },
    
    play(audioFile) {
        const audioPath = `/data/output/${currentProject}/audio/${audioFile}`;
        
        if (this.currentTrack === audioFile) return; // Already playing
        
        // Fade out old track
        if (this.audioElement && this.audioElement.src) {
            this.audioElement.volume = 0;
        }
        
        // Fade in new track
        this.audioElement.src = audioPath;
        this.audioElement.volume = 0;
        this.audioElement.play().catch(e => console.log("Audio play blocked:", e));
        
        // Fade in over 2 seconds
        let vol = 0;
        const fadeInterval = setInterval(() => {
            vol = Math.min(vol + 0.1, 0.6);
            this.audioElement.volume = vol;
            if (vol >= 0.6) clearInterval(fadeInterval);
        }, 200);
        
        this.currentTrack = audioFile;
    },
    
    stop() {
        if (this.audioElement) {
            this.audioElement.volume = 0;
            this.audioElement.pause();
            this.currentTrack = null;
        }
    }
};



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
        } else if (tag.startsWith("AMBIENCE:") || tag.startsWith("AUDIO:")) {
            // Audio tag format: # AMBIENCE: rain.mp3 or # AUDIO: forest_ambient
            const parts = tag.split(":");
            let audioFile = parts[1].trim();
            
            // Add .mp3 extension if not present
            if (!audioFile.includes(".")) {
                audioFile += ".mp3";
            }
            
            audioManager.play(audioFile);
        } else if (tag.toUpperCase() === "SILENCE" || tag.toUpperCase() === "STOP_AUDIO") {
            audioManager.stop();
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

function isSceneTransition(tags) {
    if (!tags || tags.length === 0) return false;
    return tags.some(t => {
        const tag = t.toUpperCase();
        // It is a scene transition ONLY if it is a main background IMAGE
        // We exclude items and rewards to prevent false positives
        return tag.includes('IMAGE') && 
              !tag.includes('REWARD') && 
              !tag.includes('ITEM');
    });
}