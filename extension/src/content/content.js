// content.js — Simplified, automation-ready recorder

// Initialize noise reducer (loaded from noiseReduction.js)
const noiseReducer = new NoiseReducer();

function recordEvent(event) {
    const processed = noiseReducer.processEvent(event);
    if (!processed) return; // Filtered out by noise reducer

    try {
        chrome.runtime.sendMessage({
            action: 'RECORD_EVENT',
            event: processed
        }, (response) => {
            // Check for context invalidation
            if (chrome.runtime.lastError) {
                console.warn('AutoPattern: Extension context invalidated. Please reload this page.');
                return;
            }
        });
    } catch (error) {
        // Extension was reloaded - silently fail
        console.warn('AutoPattern: Extension context lost. Please reload this page.');
    }
}

// ---------- Helpers ----------
function debounce(fn, delay) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), delay);
    };
}

function getXPath(el) {
    if (!el) return null;
    let path = '';
    while (el && el.nodeType === 1) {
        let idx = 1;
        let sib = el.previousSibling;
        while (sib) {
            if (sib.nodeType === 1 && sib.nodeName === el.nodeName) idx++;
            sib = sib.previousSibling;
        }
        path = `/${el.nodeName.toLowerCase()}[${idx}]` + path;
        el = el.parentNode;
    }
    return path;
}

function getSelector(el) {
    if (!el) return null;

    // 1. ID is most specific
    if (el.id) return `#${el.id}`;

    // 2. data-testid or aria-label
    if (el.getAttribute('data-testid')) {
        return `[data-testid="${el.getAttribute('data-testid')}"]`;
    }
    if (el.getAttribute('aria-label')) {
        return `[aria-label="${el.getAttribute('aria-label')}"]`;
    }

    // 3. Classes
    if (el.className && typeof el.className === 'string') {
        const classes = el.className.split(' ').filter(c => c.trim().length > 0 && !c.includes('hover') && !c.includes('active') && !c.includes('focus'));
        if (classes.length > 0) {
            return `${el.tagName.toLowerCase()}.${classes.join('.')}`;
        }
    }

    // 4. Name attribute (for inputs)
    if (el.name) {
        return `${el.tagName.toLowerCase()}[name="${el.name}"]`;
    }

    return null;
}

function getParentButtonOrAnchor(el) {
    while (el && el !== document.body) {
        if (el.tagName === 'BUTTON' || el.tagName === 'A') {
            return el;
        }
        el = el.parentElement;
    }
    return null;
}

// ---------- Event Builder ----------
function buildEvent(type, el, extra = {}) {
    return {
        event: type,
        timestamp: Date.now(),
        url: location.href,
        title: document.title,

        automation: {
            selector: getSelector(el),
            xpath: getXPath(el),
            tag: el?.tagName || null,
            inputType: el?.getAttribute?.('type') || null
        },

        raw: extra
    };
}

// ---------- CLICK ----------
document.addEventListener('click', e => {
    let target = e.target;

    // If we click inside a button or link (e.g. SVG or span), use the parent as the target
    const parentInteractive = getParentButtonOrAnchor(target);
    if (parentInteractive) {
        target = parentInteractive;
    }

    recordEvent(buildEvent('click', target, {
        text: target.innerText?.trim().slice(0, 80) || target.getAttribute('aria-label') || null
    }));
}, true);

// ---------- INPUT ----------
document.addEventListener('input', debounce(e => {
    const isPassword = e.target.type === 'password';
    recordEvent(buildEvent('input', e.target, {
        value: isPassword ? '[MASKED]' : (e.target.value || ''),
        length: e.target.value?.length || 0,
        fieldName: e.target.name || e.target.id || e.target.placeholder || null
    }));
}, 300), true);

// ---------- SCROLL ----------
let lastScroll = window.scrollY;
const scrollHandler = debounce(() => {
    const delta = Math.abs(window.scrollY - lastScroll);
    if (delta > 120) {
        lastScroll = window.scrollY;
        recordEvent(buildEvent('scroll', null, {
            y: window.scrollY
        }));
    }
}, 200);
window.addEventListener('scroll', scrollHandler, { passive: true });

// ---------- NAVIGATION ----------
if (!window.__pageVisitRecorded) {
    window.__pageVisitRecorded = true;
    recordEvent(buildEvent('page_visit', null));
}

(function () {
    const push = history.pushState;
    history.pushState = function () {
        push.apply(history, arguments);
        recordEvent(buildEvent('navigation', null));
    };
})();
