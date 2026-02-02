// Initialize Ink Engine
let story;
const storyContainer = document.querySelector('#story-text');
const choicesContainer = document.querySelector('#choices-container');
const imageElement = document.querySelector('#scene-image');

// Load the compiled JSON version of your .ink file
fetch('adventure.json')
    .then(response => response.json())
    .then(storyJson => {
        story = new inkjs.Story(storyJson);
        continueStory();
    });

function continueStory() {
    let content = "";
    
    // 1. Clear UI
    storyContainer.innerHTML = "";
    choicesContainer.innerHTML = "";

    // 2. Read all text until choices or end
    while (story.canContinue) {
        let line = story.Continue();
        content += `<p>${line}</p>`;

        // 3. Check for our Metadata Tags
        handleTags(story.currentTags);
    }

    storyContainer.innerHTML = content;

    // 4. Render Choices
    story.currentChoices.forEach(choice => {
        let btn = document.createElement('button');
        btn.innerText = choice.text;
        btn.classList.add('choice-btn');
        btn.onclick = () => {
            story.ChooseChoiceIndex(choice.index);
            continueStory();
        };
        choicesContainer.appendChild(btn);
    });
}

function handleTags(tags) {
    if (!tags) return;
    tags.forEach(tag => {
        if (tag.startsWith("IMAGE:")) {
            const imageName = tag.split(":")[1].trim();
            imageElement.src = `data/assets/${imageName}.png`;
        }
    });
}