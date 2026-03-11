async function fetchImageAsDataUrl(url) {
	const response = await fetch(url);
	if (!response.ok) {
		throw new Error(`Image fetch failed (${response.status}) for ${url}`);
	}
	const blob = await response.blob();
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onloadend = () => resolve(reader.result);
		reader.onerror = reject;
		reader.readAsDataURL(blob);
	});
}

function formatDate(iso) {
	if (!iso) return new Date().toLocaleDateString();
	const dt = new Date(iso);
	if (Number.isNaN(dt.getTime())) return new Date().toLocaleDateString();
	return dt.toLocaleDateString();
}

function sanitizeTitle(text) {
	return String(text || '')
		.replace(/[_\-]+/g, ' ')
		.split(/\s+/)
		.filter(Boolean)
		.map(part => part.charAt(0).toUpperCase() + part.slice(1))
		.join(' ');
}

function detectImageFormat(dataUrl) {
	if (typeof dataUrl !== 'string') return 'JPEG';
	if (dataUrl.includes('image/png')) return 'PNG';
	if (dataUrl.includes('image/webp')) return 'WEBP';
	return 'JPEG';
}

window.generateAdventurePdf = async function generateAdventurePdf(payload) {
	if (!window.jspdf || !window.jspdf.jsPDF) {
		throw new Error('jsPDF is not loaded.');
	}

	const { jsPDF } = window.jspdf;
	const doc = new jsPDF({ unit: 'pt', format: 'a4' });

	const pageWidth = doc.internal.pageSize.getWidth();
	const pageHeight = doc.internal.pageSize.getHeight();
	const marginX = 48;
	const marginTop = 52;
	const marginBottom = 62;
	const maxTextWidth = pageWidth - (marginX * 2);
	let y = marginTop;

	const ensureSpace = (heightNeeded = 24) => {
		if (y + heightNeeded > pageHeight - marginBottom) {
			doc.addPage();
			y = marginTop;
		}
	};

	const addHeading = (text, size = 18) => {
		ensureSpace(34);
		doc.setFont('times', 'bold');
		doc.setFontSize(size);
		doc.setTextColor(30, 30, 30);
		doc.text(text, marginX, y);
		y += size + 8;
	};

	const addSceneHeading = (text) => {
		ensureSpace(30);
		doc.setFont('times', 'bold');
		doc.setFontSize(15);
		doc.setTextColor(88, 68, 28);
		doc.text(text, marginX, y);
		y += 22;
	};

	const addParagraph = (text, size = 12, style = 'normal', color = [45, 45, 45]) => {
		const safeText = String(text || '').trim();
		if (!safeText) return;
		doc.setFont('times', style);
		doc.setFontSize(size);
		doc.setTextColor(color[0], color[1], color[2]);
		const lines = doc.splitTextToSize(safeText, maxTextWidth);
		const lineHeight = Math.max(16, size + 4);
		ensureSpace((lines.length * lineHeight) + 4);
		doc.text(lines, marginX, y);
		y += (lines.length * lineHeight) + 4;
	};

	addHeading('Lume & Lore Adventure Log', 24);
	const storyTitle = payload.projectTitle || sanitizeTitle(payload.projectId || 'Unknown Adventure');
	addParagraph(storyTitle, 15, 'bold');
	addParagraph(
		`You have played as: ${payload.protagonistName || 'Unknown'} on ${formatDate(payload.createdAt)}`,
		11,
		'italic'
	);
	y += 10;

	addHeading('Story Flow', 18);

	let lastRenderedSceneKey = null;

	const flow = Array.isArray(payload.flow) ? payload.flow : [];
	for (let idx = 0; idx < flow.length; idx++) {
		const entry = flow[idx];
		const nextEntry = flow[idx + 1];
		const entryType = String(entry?.type || '').toLowerCase();

		if (entryType === 'scene') {
			const sceneKey = entry.sceneKey || '';
			const sceneTitle = entry.sceneTitle || sanitizeTitle(sceneKey || 'Scene');
			if (sceneKey !== lastRenderedSceneKey) {
				addSceneHeading(sceneTitle);
				lastRenderedSceneKey = sceneKey;
			}
			addParagraph(entry.text || '', 12, 'normal');
			continue;
		}

		if (entryType === 'narration') {
			addParagraph(entry.text || '', 12, 'normal');
			continue;
		}

		if (entryType === 'choice') {
			addParagraph(`Choice selected: ${entry.text || ''}`, 12, 'italic', [60, 45, 20]);
			continue;
		}

		if (entryType === 'outcome') {
			const thisText = String(entry.text || '').trim();
			const nextIsSameSceneText =
				nextEntry &&
				String(nextEntry.type || '').toLowerCase() === 'scene' &&
				String(nextEntry.text || '').trim() === thisText;
			if (nextIsSameSceneText) {
				continue;
			}
			addParagraph(`Result: ${thisText}`, 12, 'normal', [50, 50, 50]);
			continue;
		}

		if (entryType === 'trait_change') {
			const sign = entry.delta > 0 ? '+' : '';
			addParagraph(
				`↳ Trait change: ${entry.traitLabel || entry.trait}: ${entry.from} → ${entry.to} (${sign}${entry.delta})`,
				11,
				'italic',
				[35, 85, 45]
			);
			continue;
		}

		if (entryType === 'image') {
			if (entry.imagePath) {
				try {
					const dataUrl = await fetchImageAsDataUrl(entry.imagePath);
					const imgProps = doc.getImageProperties(dataUrl);
					const maxImageWidth = maxTextWidth;
					const maxImageHeight = 220;
					const scale = Math.min(maxImageWidth / imgProps.width, maxImageHeight / imgProps.height);
					const renderWidth = imgProps.width * scale;
					const renderHeight = imgProps.height * scale;

					ensureSpace(renderHeight + 12);
					doc.addImage(dataUrl, detectImageFormat(dataUrl), marginX, y, renderWidth, renderHeight);
					y += renderHeight + 8;
				} catch (e) {
					addParagraph('[Image could not be embedded in this export.]', 10, 'italic', [130, 60, 60]);
				}
			}
			continue;
		}

		if (entryType === 'ending') {
			addParagraph(entry.text || 'Story reached its ending.', 12, 'bold', [20, 80, 20]);
		}
	}

	y += 8;
	addHeading('Final Traits', 18);
	if (!payload.finalTraits || payload.finalTraits.length === 0) {
		addParagraph('No tracked traits available for this adventure.', 12);
	} else {
		payload.finalTraits.forEach(trait => {
			addParagraph(`${trait.label}: ${trait.value}`, 12);
		});
	}

	y += 14;
	addParagraph('This document was created with the Lume&Lore software.', 10, 'italic', [90, 90, 90]);

	const pageCount = doc.getNumberOfPages();
	for (let page = 1; page <= pageCount; page++) {
		doc.setPage(page);
		doc.setFont('times', 'normal');
		doc.setFontSize(10);
		doc.setTextColor(110, 110, 110);
		doc.text(`Page ${page} of ${pageCount}`, pageWidth / 2, pageHeight - 28, { align: 'center' });
	}

	const safeProject = String(payload.projectId || 'adventure').replace(/[^a-z0-9_-]/gi, '_');
	doc.save(`${safeProject}_adventure_${Date.now()}.pdf`);
};
