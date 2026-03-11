// --- GLOBAL STATE ---
let story;
let currentProject = "";
let unlockedImages = { scenes: [], rewards: [] };
let activeGalleryTab = 'scenes';
let trackedTraits = [];
let lastTraitValues = {};
const MAX_TRACKED_TRAITS = 3;
const NON_TRAIT_VARIABLES = new Set(['protagonist_name', 'protagonist_bio', 'last_node']);
const settings = {
    typewriterEnabled: true,
    typewriterSpeed: 50 // ms per character
};

let adventureFlowLog = [];
let traitChangeLog = [];
let storySessionStartedAt = null;
let storyReachedEnding = false;
let flowStepCounter = 0;
let sceneTitleLookup = {};
let currentRenderedSceneKey = null;


// UI References
const storyContainer = document.querySelector('#story-text');
const choicesContainer = document.querySelector('#choices-container');
const imageElement = document.querySelector('#scene-image');
const rewardBanner = document.querySelector('#reward-banner');
const traitsPanel = document.querySelector('#traits-panel');

function clampTraitValue(value) {
    return Math.max(0, Math.min(100, Math.round(value)));
}

function getTextPane() {
    return document.getElementById('text-container');
}

function easeInOutCubic(t) {
    return t < 0.5
        ? 4 * t * t * t
        : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function animateTextPaneScrollTo(targetTop, duration = 1200) {
    const textPane = getTextPane();
    if (!textPane) return;

    const startTop = textPane.scrollTop;
    const clampedTarget = Math.max(0, targetTop);
    const distance = clampedTarget - startTop;

    if (Math.abs(distance) < 2) {
        textPane.scrollTop = clampedTarget;
        return;
    }

    const startTime = performance.now();
    const step = now => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeInOutCubic(progress);
        textPane.scrollTop = startTop + (distance * eased);
        if (progress < 1) {
            requestAnimationFrame(step);
        }
    };

    requestAnimationFrame(step);
}

function scrollStoryToBottom(duration = 1300) {
    const textPane = getTextPane();
    if (!textPane) return;
    animateTextPaneScrollTo(textPane.scrollHeight, duration);
}

function formatTraitName(name) {
    return name
        .split(/[_\s]+/)
        .filter(Boolean)
        .map(part => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
}

function getVariablesStateSnapshot() {
    if (!story) return {};
    const variables = {};
    try {
        const varsState = story.variablesState;
        if (!varsState) return {};
        const keys = Object.keys(varsState);
        keys.forEach(key => {
            variables[key] = varsState[key];
        });
    } catch (e) {
        console.warn("Could not read story variables for trait tracking:", e);
    }
    return variables;
}

function normalizeTags(tags) {
    return Array.isArray(tags) ? tags.filter(Boolean).map(tag => String(tag)) : [];
}

function extractImageFromTags(tags) {
    const imageTag = normalizeTags(tags).find(tag => tag.startsWith('IMAGE:'));
    if (!imageTag) return null;
    return imageTag.split(':').slice(1).join(':').trim();
}

function sceneKeyFromImageFile(fileName) {
    if (!fileName) return null;
    return String(fileName)
        .replace(/\.[^/.]+$/, '')
        .replace(/_(main|reward)$/i, '')
        .trim();
}

function formatSceneTitle(sceneKey) {
    if (!sceneKey) return 'Untitled Scene';
    return String(sceneKey)
        .split(/[_\s]+/)
        .filter(Boolean)
        .map(part => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
}

function getSceneMetadataFromTags(tags) {
    const imageFile = extractImageFromTags(tags);
    const sceneKey = sceneKeyFromImageFile(imageFile);
    const sceneTitle = sceneTitleLookup[sceneKey] || formatSceneTitle(sceneKey);
    return { sceneKey, sceneTitle, imageFile };
}

function buildSceneTitleLookupFromAdventure(adventureJson) {
    const lookup = {};
    const root = Array.isArray(adventureJson?.root) ? adventureJson.root : null;
    const rootObj = root && typeof root[2] === 'object' ? root[2] : null;
    if (!rootObj) return lookup;

    Object.keys(rootObj).forEach(key => {
        if (!key || typeof key !== 'string') return;
        if (key === 'start_node' || key === 'global decl') return;
        if (key.includes('_result_') || key.endsWith('_next')) return;
        const nodeValue = rootObj[key];
        if (!Array.isArray(nodeValue) && typeof nodeValue !== 'string') return;
        lookup[key] = formatSceneTitle(key);
    });

    return lookup;
}

function renderSceneHeaderIfNeeded(sceneKey, sceneTitle) {
    if (!sceneKey || !sceneTitle) return;
    if (currentRenderedSceneKey === sceneKey) return;
    const header = document.createElement('h2');
    header.className = 'scene-header';
    header.innerText = sceneTitle;
    storyContainer.appendChild(header);
    currentRenderedSceneKey = sceneKey;
}

function removeLastOutcomeFlowEntryByText(text) {
    const target = String(text || '').trim();
    if (!target) return;
    for (let idx = adventureFlowLog.length - 1; idx >= 0; idx--) {
        const entry = adventureFlowLog[idx];
        if (!entry) continue;
        if (entry.type === 'outcome' && String(entry.text || '').trim() === target) {
            adventureFlowLog.splice(idx, 1);
            break;
        }
    }
}

function resetAdventureTracking() {
    adventureFlowLog = [];
    traitChangeLog = [];
    flowStepCounter = 0;
    storyReachedEnding = false;
    storySessionStartedAt = new Date().toISOString();
    currentRenderedSceneKey = null;
}

function addFlowEntry(type, payload = {}) {
    const entry = {
        step: ++flowStepCounter,
        type,
        timestamp: new Date().toISOString(),
        ...payload
    };
    adventureFlowLog.push(entry);
    return entry;
}

function getTrackedTraitSnapshot() {
    const vars = getVariablesStateSnapshot();
    return trackedTraits.map(name => ({
        name,
        label: formatTraitName(name),
        value: clampTraitValue(typeof vars[name] === 'number' ? vars[name] : 0)
    }));
}

function buildAdventureExportPayload() {
    const vars = getVariablesStateSnapshot();
    const selector = document.getElementById('project-selector');
    const selectedOption = selector && selector.options ? selector.options[selector.selectedIndex] : null;
    return {
        projectId: currentProject,
        projectTitle: selectedOption ? selectedOption.text : formatSceneTitle(currentProject),
        createdAt: new Date().toISOString(),
        startedAt: storySessionStartedAt,
        protagonistName: String(vars.protagonist_name || ''),
        flow: [...adventureFlowLog],
        traitChanges: [...traitChangeLog],
        finalTraits: getTrackedTraitSnapshot()
    };
}

function detectTrackedTraits() {
    const variables = getVariablesStateSnapshot();
    const candidateTraits = Object.entries(variables)
        .filter(([name, value]) => {
            if (NON_TRAIT_VARIABLES.has(name)) return false;
            if (typeof name !== 'string' || name.startsWith('$')) return false;
            if (typeof value !== 'number' || !Number.isFinite(value)) return false;
            return value >= 0 && value <= 100;
        })
        .sort(([a], [b]) => a.localeCompare(b))
        .slice(0, MAX_TRACKED_TRAITS)
        .map(([name]) => name);

    trackedTraits = candidateTraits;
    lastTraitValues = {};
    trackedTraits.forEach(name => {
        const value = variables[name];
        if (typeof value === 'number') {
            lastTraitValues[name] = clampTraitValue(value);
        }
    });
}

function updateTraitsPanel(playSounds = true) {
    if (!traitsPanel || !story) return;
    if (trackedTraits.length === 0) detectTrackedTraits();

    if (trackedTraits.length === 0) {
        traitsPanel.innerHTML = "";
        traitsPanel.style.display = 'none';
        return;
    }

    const variables = getVariablesStateSnapshot();
    traitsPanel.style.display = 'grid';
    traitsPanel.innerHTML = "";

    trackedTraits.forEach(name => {
        const raw = variables[name];
        if (typeof raw !== 'number' || !Number.isFinite(raw)) return;

        const value = clampTraitValue(raw);
        const previous = lastTraitValues[name];
        const delta = (typeof previous === 'number') ? value - previous : 0;

        const card = document.createElement('div');
        card.className = 'trait-card';

        const row = document.createElement('div');
        row.className = 'trait-row';

        const label = document.createElement('span');
        label.className = 'trait-name';
        label.innerText = formatTraitName(name);

        const valueWrap = document.createElement('div');
        valueWrap.className = 'trait-value-wrap';

        const valueEl = document.createElement('span');
        valueEl.className = 'trait-value';
        valueEl.innerText = String(value);

        const deltaEl = document.createElement('span');
        deltaEl.className = 'trait-delta';

        if (delta !== 0) {
            deltaEl.classList.add('show', delta > 0 ? 'up' : 'down');
            deltaEl.innerText = `${delta > 0 ? '+' : ''}${delta}`;
            card.classList.add(delta > 0 ? 'trait-up' : 'trait-down');
            const traitChange = {
                step: flowStepCounter,
                timestamp: new Date().toISOString(),
                trait: name,
                traitLabel: formatTraitName(name),
                from: previous,
                to: value,
                delta
            };
            traitChangeLog.push(traitChange);
            addFlowEntry('trait_change', traitChange);
            if (playSounds) {
                traitSoundManager.playDelta(delta);
            }
            setTimeout(() => {
                card.classList.remove('trait-up', 'trait-down');
                deltaEl.classList.remove('show', 'up', 'down');
            }, 900);
        }

        const bar = document.createElement('div');
        bar.className = 'trait-bar';
        const fill = document.createElement('div');
        fill.className = 'trait-fill';
        fill.style.width = `${value}%`;
        bar.appendChild(fill);

        valueWrap.appendChild(valueEl);
        valueWrap.appendChild(deltaEl);

        row.appendChild(label);
        row.appendChild(valueWrap);

        card.appendChild(row);
        card.appendChild(bar);
        traitsPanel.appendChild(card);

        lastTraitValues[name] = value;
    });

    if (!traitsPanel.children.length) {
        traitsPanel.style.display = 'none';
    }
}

// --- INITIALIZATION ---
// --- UI RESET/CLEANUP HELPER ---
function resetGameUI() {
    // Hide overlays and menu
    const mainMenu = document.getElementById('main-menu');
    if (mainMenu) {
        mainMenu.style.display = 'none';
        mainMenu.classList.remove('overlay');
        mainMenu.setAttribute('aria-hidden', 'true');
        mainMenu.style.zIndex = '0';
    }
    const gallery = document.getElementById('gallery-overlay');
    if (gallery) {
        gallery.style.display = 'none';
        gallery.classList.remove('overlay');
    }
    const statusBar = document.getElementById('status-bar');
    if (statusBar) statusBar.style.display = 'none';
    const gameContainer = document.getElementById('game-container');
    if (gameContainer) gameContainer.style.display = 'grid';
    if (imageElement) {
        imageElement.src = "";
        imageElement.style.opacity = 0;
    }
    if (traitsPanel) {
        traitsPanel.innerHTML = "";
        traitsPanel.style.display = 'none';
    }
    if (storyContainer) storyContainer.innerHTML = "";
}
// --- ASSET PATH HELPER ---
function getAssetPath(type, fileName = "") {
    // type: 'assets', 'audio', etc.
    // fileName: optional file name to append
    if (!currentProject) return "";
    let base = `/data/output/${currentProject}/`;
    if (type === 'assets') base += 'assets/';
    if (type === 'audio') base += 'audio/';
    if (fileName) base += fileName;
    return base;
}
window.onload = () => {
    // Restore typewriter setting from localStorage
    const saved = localStorage.getItem('typewriter_enabled');
    if (saved !== null) {
        settings.typewriterEnabled = saved === 'true';
    }
    loadManifest();
};

function loadManifest() {
    checkResumeStatus();
    const selector = document.getElementById('project-selector');
    const manifestPath = '../data/output/manifest.json';
    // ...existing code...

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
    trackedTraits = [];
    lastTraitValues = {};
    // ...existing code...
    if (!currentProject) {
        alert("Please select an adventure from the list first.");
        return;
    }

    resetAdventureTracking();
    sceneTitleLookup = {};
    
    // Initialize audio manager
    audioManager.init();
    traitSoundManager.init();
    
    // 1. Load Gallery Progress
    const storedArt = localStorage.getItem(`unlocked_art_${currentProject}`);
    if (storedArt) unlockedImages = JSON.parse(storedArt);
    if (storyContainer) storyContainer.innerHTML = "";

    // Reset UI for new game
    resetGameUI();
    
    const expectedPath = getAssetPath('assets', '../adventure.json');
    fetch(expectedPath)
        .then(r => {
            if (!r.ok) {
                throw new Error(`Failed to load adventure.json (HTTP ${r.status})`);
            }
            return r.json();
        })
        .then(json => loadStory(json, saveData))
        .catch(e => {
            console.error("Could not load adventure.json", e);
            const folder = expectedPath.replace(/adventure\.json.*/, '');
            alert(
                `Error: Could not find adventure.json.\n\n` +
                `Expected location: ${folder}\n\n` +
                `Please place your adventure.json file in this folder and try again.\n\n` +
                `Details: ${e.message}`
            );
        });
}

// --- STORY LOADING LOGIC ---
function loadStory(json, saveData = null) {
    if (typeof inkjs === 'undefined') {
        alert("CRITICAL ERROR: 'ink.js' not found. Please ensure ink.js is included in your project.");
        return;
    }
    try {
        sceneTitleLookup = buildSceneTitleLookupFromAdventure(json);
        story = new inkjs.Story(json);
        resetGameUI();
        if (saveData) {
            try {
                story.state.LoadJson(saveData);
            } catch (e) {
                alert("Error: Failed to load save data. The file may be corrupted or incompatible.\n\n" + e.message);
                console.error("Save Load Error:", e);
            }
        }
        detectTrackedTraits();
        addFlowEntry('session_start', {
            mode: saveData ? 'resumed' : 'new',
            note: saveData ? 'Journey resumed from save data.' : 'New journey started.'
        });
        updateTraitsPanel(false);
        continueStory();
    } catch (e) {
        alert("Error: Failed to initialize the story. The adventure data may be corrupted or incompatible.\n\n" + e.message);
        console.error("Story Init Error:", e);
    }
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
    
    let loopCount = 0;
    while (story.canContinue) {
        loopCount++;
        const text = story.Continue();
        const tags = story.currentTags;
        const sceneTransition = isSceneTransition(tags);
        const sceneMeta = getSceneMetadataFromTags(tags);
        if (sceneTransition) {
            renderSceneHeaderIfNeeded(sceneMeta.sceneKey, sceneMeta.sceneTitle);
        }
        // ...existing code...
        const paragraph = document.createElement('p');
        if (tags && tags.length > 0) paragraph.setAttribute('data-tags', tags.join('|'));
        storyContainer.appendChild(paragraph);

        // If this paragraph has an IMAGE tag, show the image only when typewriter starts
        let imageTag = null;
        if (tags && tags.length > 0) {
            imageTag = tags.find(t => t.startsWith("IMAGE:"));
        }

        if (settings.typewriterEnabled) {
            if (imageTag) {
                // Show image immediately before typewriter starts
                handleTags([imageTag]);
                // Remove IMAGE tag from tags for further handling (avoid double handling)
                const otherTags = tags.filter(t => t !== imageTag);
                typewriterEffect(text, paragraph, settings.typewriterSpeed);
                handleTags(otherTags);
            } else {
                typewriterEffect(text, paragraph, settings.typewriterSpeed);
                handleTags(tags);
            }
        } else {
            paragraph.innerText = text;
            handleTags(tags);
        }

        const trimmedText = String(text || '').trim();
        if (trimmedText.length > 0) {
            addFlowEntry(sceneTransition ? 'scene' : 'narration', {
                text: trimmedText,
                tags: normalizeTags(tags),
                image: sceneMeta.imageFile,
                sceneKey: sceneMeta.sceneKey,
                sceneTitle: sceneMeta.sceneTitle
            });
        }
    }
    updateTraitsPanel(true);
    renderChoices();

    // If no text was produced immediately, defer a check to allow typewriter to start.
    setTimeout(() => {
        const paras = storyContainer.querySelectorAll('p');
        const hasNonEmpty = Array.from(paras).some(p => p.innerText && p.innerText.trim() !== '');
        // If no paragraphs exist, check whether the ink engine actually has text available to push
        if (!hasNonEmpty && paras.length === 0 && story.currentChoices && story.currentChoices.length > 0) {
            if (story.currentText && story.currentText.trim().length > 0) {
                const p = document.createElement('p');
                if (settings.typewriterEnabled) typewriterEffect(story.currentText, p, settings.typewriterSpeed);
                else p.innerText = story.currentText;
                if (story.currentTags && story.currentTags.length > 0) p.setAttribute('data-tags', (story.currentTags || []).join('|'));
                storyContainer.appendChild(p);
                if (story.currentTags && story.currentTags.length > 0) handleTags(story.currentTags);
                renderChoices();
                return;
            }
        }
        scrollStoryToBottom(1200);
    }, 300);

    requestAnimationFrame(() => {
        scrollStoryToBottom(1400);
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
    settings.typewriterEnabled = !settings.typewriterEnabled;
    const btn = document.getElementById('typewriter-toggle');
    if (btn) {
        btn.innerText = settings.typewriterEnabled ? "⌨️ Typewriter ON" : "⌨️ Typewriter OFF";
    }
    localStorage.setItem('typewriter_enabled', settings.typewriterEnabled);
}

function getOutcomeToneFromTags(tags) {
    const normalized = (tags || []).map(tag => String(tag || '').replace(/^#/, '').trim().toLowerCase());
    if (normalized.includes('bad')) return 'bad';
    if (normalized.includes('good')) return 'good';
    return 'neutral';
}

function applyOutcomeToneToParagraph(paragraph, tone) {
    if (!paragraph) return;
    paragraph.classList.remove('outcome-good', 'outcome-bad', 'outcome-neutral');
    paragraph.classList.add(`outcome-${tone || 'neutral'}`);
}

function applyOutcomeToneToFragment(fragment, tone) {
    if (!fragment || !fragment.childNodes) return;
    Array.from(fragment.childNodes).forEach(node => {
        if (node && node.tagName && node.tagName.toLowerCase() === 'p' && node.classList.contains('outcome-text')) {
            applyOutcomeToneToParagraph(node, tone);
        }
    });
}

function renderChoices() {
    choicesContainer.innerHTML = "";
    if (story.currentChoices.length === 0 && !story.canContinue) {
        // end of story reached
        if (!storyReachedEnding) {
            const congrats = document.createElement('p');
            congrats.className = 'congrats-msg';
            congrats.innerText = "🎉 Congratulations! You've reached the end of this adventure.";
            storyContainer.appendChild(congrats);

            const saveHint = document.createElement('p');
            saveHint.className = 'end-save-hint';
            saveHint.innerText = "You can now save a complete PDF log of your journey.";
            storyContainer.appendChild(saveHint);

            addFlowEntry('ending', {
                text: 'Story ended. Export option displayed to save the full adventure.'
            });
            storyReachedEnding = true;
        }

        // Save adventure button
        const saveBtn = document.createElement('button');
        saveBtn.id = 'save-adventure-pdf-btn';
        saveBtn.className = 'choice-btn primary';
        saveBtn.innerText = "📜 Save Adventure (PDF)";
        saveBtn.onclick = downloadStoryLog;
        choicesContainer.appendChild(saveBtn);

        // Return to menu button
        const endBtn = document.createElement('button');
        endBtn.className = 'choice-btn';
        endBtn.innerText = "🏠 Return to Menu";
        endBtn.onclick = () => location.reload();
        choicesContainer.appendChild(endBtn);
        return;
    }
    story.currentChoices.forEach(choice => {
        let isBad = false;
        let isExquisite = false;
        const button = document.createElement('button');
        button.innerText = choice.text;
        button.className = "choice-btn";
        if (choice.tags && choice.tags.length > 0) button.setAttribute('data-tags', (choice.tags || []).join('|'));
        const choiceTone = getOutcomeToneFromTags(choice.tags || []);
        if (choiceTone === 'bad') isBad = true;
        const lowerText = (choice.text || '').toLowerCase();
        if (lowerText.includes('bad')) isBad = true;
        if (lowerText.includes('exquisite')) isExquisite = true;

        button.onclick = () => {
            Array.from(choicesContainer.children).forEach(btn => {
                if (btn !== button) {
                    btn.style.display = 'none';
                } else {
                    btn.classList.add('selected-choice');
                    btn.disabled = true;
                }
            });

            const selectedChoiceParagraph = document.createElement('p');
            selectedChoiceParagraph.className = 'player-choice-line';
            selectedChoiceParagraph.innerText = `→ ${choice.text}`;
            storyContainer.appendChild(selectedChoiceParagraph);
            addFlowEntry('choice', {
                text: String(choice.text || '').trim(),
                tags: normalizeTags(choice.tags || [])
            });
            scrollStoryToBottom(1000);

            // 1. Commit Choice
            story.ChooseChoiceIndex(choice.index);
            if (choice.tags && choice.tags.length > 0) handleTags(choice.tags);
            let nextSceneBuffer = null;
            const outcomeFragment = document.createDocumentFragment();
            let outcomeTone = 'neutral';

            // 3. Process Outcome Text
            while (story.canContinue) {
                const text = story.Continue();
                const tags = story.currentTags || [];
                const taggedTone = getOutcomeToneFromTags(tags);
                if (taggedTone !== 'neutral') {
                    outcomeTone = taggedTone;
                    applyOutcomeToneToFragment(outcomeFragment, outcomeTone);
                }

                const normalizedText = String(text || '').trim().replace(/^#/, '').trim().toLowerCase();
                if (normalizedText === 'good' || normalizedText === 'bad') {
                    outcomeTone = normalizedText;
                    applyOutcomeToneToFragment(outcomeFragment, outcomeTone);
                    continue;
                }

                const _lower = text.toLowerCase();
                if (_lower.includes("fate frowns") || _lower.includes("bad") || _lower.includes("good")) {
                    continue;
                }
                if (isSceneTransition(tags)) {
                    if (text.trim().length === 0 && story.canContinue) {
                        const nextChunk = story.Continue();
                        const nextTags = story.currentTags || [];
                        const effectiveText = (nextChunk && nextChunk.trim().length > 0) ? nextChunk : text;
                        nextSceneBuffer = { text: effectiveText, tags: (tags || []).concat(nextTags) };
                    } else {
                        nextSceneBuffer = { text, tags };
                    }
                    break;
                } else {
                    if (text.trim().length > 0) {
                        const p = document.createElement('p');
                        p.innerText = text;
                        p.className = `outcome-text outcome-${outcomeTone}`;
                        if (tags && tags.length > 0) p.setAttribute('data-tags', tags.join('|'));
                        outcomeFragment.appendChild(p);
                        addFlowEntry('outcome', {
                            text: String(text || '').trim(),
                            tone: outcomeTone,
                            tags: normalizeTags(tags)
                        });
                    }
                    handleTags(tags);
                }
            }

            updateTraitsPanel(true);

            // 4. Create "Proceed" Button
            const hasBadOutcome = isBad || outcomeTone === 'bad';
            let btnText = "Proceed to next scene";
            if (isExquisite) btnText = "Excellent choice - proceed to next scene";
            if (hasBadOutcome) btnText = "This path leads you astray. Try another choice.";

            const proceedBtn = document.createElement('button');
            proceedBtn.className = "choice-btn primary";
            proceedBtn.innerText = btnText;
            proceedBtn.style.width = "100%";
            proceedBtn.style.marginTop = "2rem";
            if (isExquisite) {
                proceedBtn.style.borderColor = "gold";
                proceedBtn.style.color = "gold";
            }
            if (hasBadOutcome) {
                proceedBtn.style.borderColor = "black";
                proceedBtn.style.color = "#000000";
            }
            if (choice.tags && choice.tags.length > 0) proceedBtn.setAttribute('data-choice-tags', (choice.tags || []).join('|'));

            proceedBtn.onclick = () => {
                if (nextSceneBuffer) {
                    if (nextSceneBuffer.text && nextSceneBuffer.text.trim().length > 0) {
                        const sceneMeta = getSceneMetadataFromTags(nextSceneBuffer.tags || []);
                        if (isSceneTransition(nextSceneBuffer.tags || [])) {
                            renderSceneHeaderIfNeeded(sceneMeta.sceneKey, sceneMeta.sceneTitle);
                        }
                        const p = document.createElement('p');
                        if (settings.typewriterEnabled) {
                            typewriterEffect(nextSceneBuffer.text, p, settings.typewriterSpeed);
                        } else {
                            p.innerText = nextSceneBuffer.text;
                        }
                        storyContainer.appendChild(p);
                        addFlowEntry(isSceneTransition(nextSceneBuffer.tags || []) ? 'scene' : 'narration', {
                            text: String(nextSceneBuffer.text || '').trim(),
                            tags: normalizeTags(nextSceneBuffer.tags || []),
                            image: sceneMeta.imageFile,
                            sceneKey: sceneMeta.sceneKey,
                            sceneTitle: sceneMeta.sceneTitle
                        });
                    }
                    handleTags(nextSceneBuffer.tags);
                }

                proceedBtn.remove();
                continueStory();
            };

            // 5. If we captured a scene transition but the fragment contains the first paragraph
            if (nextSceneBuffer && (!nextSceneBuffer.text || nextSceneBuffer.text.trim().length === 0)) {
                const lastNode = outcomeFragment.lastChild;
                if (lastNode && lastNode.tagName && lastNode.tagName.toLowerCase() === 'p') {
                    const lastText = lastNode.innerText || '';
                    if (lastText.trim().length > 0) {
                        const movedTags = lastNode.getAttribute('data-tags');
                        nextSceneBuffer.text = lastText;
                        removeLastOutcomeFlowEntryByText(lastText);
                        if (movedTags) {
                            const movedArr = (movedTags || '').split('|').filter(Boolean);
                            nextSceneBuffer.tags = (nextSceneBuffer.tags || []).concat(movedArr);
                        }
                        outcomeFragment.removeChild(lastNode);
                    }
                }
            }

            storyContainer.appendChild(outcomeFragment);
            choicesContainer.innerHTML = "";
            choicesContainer.appendChild(proceedBtn);

            requestAnimationFrame(() => {
                scrollStoryToBottom(1300);
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
        const audioPath = getAssetPath('audio', audioFile);
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

const traitSoundManager = {
    audioContext: null,

    init() {
        if (this.audioContext) return;
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        try {
            this.audioContext = new AudioCtx();
        } catch (e) {
            console.log("Trait SFX unavailable:", e);
        }
    },

    playTone(frequency, durationMs = 110, gainLevel = 0.05, delaySec = 0) {
        if (!this.audioContext) return;
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume().catch(() => {});
        }

        const now = this.audioContext.currentTime + delaySec;
        const oscillator = this.audioContext.createOscillator();
        const gain = this.audioContext.createGain();

        oscillator.type = 'triangle';
        oscillator.frequency.setValueAtTime(frequency, now);

        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.exponentialRampToValueAtTime(gainLevel, now + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + (durationMs / 1000));

        oscillator.connect(gain);
        gain.connect(this.audioContext.destination);
        oscillator.start(now);
        oscillator.stop(now + (durationMs / 1000) + 0.02);
    },

    playDelta(delta) {
        if (!delta) return;
        const magnitude = Math.min(Math.abs(delta), 20);
        const loudness = 0.035 + (magnitude / 20) * 0.025;

        if (delta > 0) {
            this.playTone(590, 90, loudness, 0);
            this.playTone(760, 110, loudness, 0.07);
        } else {
            this.playTone(350, 140, loudness, 0);
            this.playTone(280, 120, loudness * 0.9, 0.09);
        }
    }
};



function handleTags(tags) {
    if (!tags || tags.length === 0) return;
    
    tags.forEach(tag => {
        if (tag.startsWith("IMAGE:")) {
            const fileName = tag.split(":")[1].trim();
            const fullPath = getAssetPath('assets', fileName);
            addFlowEntry('image', {
                imageFile: fileName,
                imagePath: fullPath,
                imageType: fileName.includes("_reward") ? 'reward' : 'scene'
            });
            if (imageElement) {
                // Preload image to prevent "pop-in"
                const tempImg = new Image();
                tempImg.src = fullPath;
                tempImg.onload = () => {
                    imageElement.style.opacity = 0; // Fade out old (start transition)
                    setTimeout(() => {
                        imageElement.src = fullPath;
                        imageElement.style.opacity = 1; 
                    }, 300);
                    requestAnimationFrame(() => {
                        scrollStoryToBottom(1200);
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
                 imageElement.classList.remove("reward-pulse");
                 imageElement.classList.add("reward-fadein");
                 rewardBanner.style.display = "block";
                 // Remove fade-in class after animation completes
                 setTimeout(() => {
                    imageElement.classList.remove("reward-fadein");
                 }, 3000);
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
        img.src = getAssetPath('assets', fileName);
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

// --- EXPORT / SAVE LOG ---

function downloadStoryLog() {
    if (!story) return;
    if (typeof window.generateAdventurePdf !== 'function') {
        alert('PDF export is unavailable. Please ensure pdf_export.js is loaded.');
        return;
    }

    const saveButton = document.getElementById('save-adventure-pdf-btn');
    const originalLabel = saveButton ? saveButton.innerText : '';
    if (saveButton) {
        saveButton.disabled = true;
        saveButton.innerText = 'Preparing PDF...';
    }

    const payload = buildAdventureExportPayload();
    window.generateAdventurePdf(payload)
        .catch(err => {
            console.error('Failed to generate PDF export:', err);
            alert('Could not generate PDF export. See console for details.');
        })
        .finally(() => {
            if (saveButton) {
                saveButton.disabled = false;
                saveButton.innerText = originalLabel || '📜 Save Adventure (PDF)';
            }
        });
}

