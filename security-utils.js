/**
 * NOVELFORGE v2.1 - Security Utilities
 * Input sanitization and XSS prevention helpers
 */

const SecurityUtils = {
    /**
     * Sanitize HTML to prevent XSS attacks
     * @param {string} html - Raw HTML string
     * @returns {string} - Sanitized HTML string
     */
    sanitizeHTML(html) {
        if (!html) return '';
        
        const temp = document.createElement('div');
        temp.textContent = html;
        return temp.innerHTML;
    },

    /**
     * Escape HTML special characters
     * @param {string} text - Plain text
     * @returns {string} - Escaped HTML string
     */
    escapeHTML(text) {
        if (!text) return '';
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Safely set innerHTML with sanitization
     * @param {HTMLElement} element - Target element
     * @param {string} html - HTML content to set
     */
    setInnerHTML(element, html) {
        if (!element) return;
        element.innerHTML = this.sanitizeHTML(html);
    },

    /**
     * Validate and sanitize user input from contenteditable fields
     * @param {string} input - User input
     * @returns {string} - Sanitized input
     */
    sanitizeInput(input) {
        if (!input) return '';
        
        // Remove script tags and event handlers
        let sanitized = input.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
        sanitized = sanitized.replace(/on\w+="[^"]*"/g, '');
        sanitized = sanitized.replace(/on\w+='[^']*'/g, '');
        
        // Allow only safe HTML tags
        const allowedTags = ['p', 'br', 'strong', 'em', 'u', 'b', 'i', 'ul', 'ol', 'li'];
        const tagRegex = new RegExp(`<(?!/?(?:${allowedTags.join('|')})\\b)[^>]*>`, 'gi');
        sanitized = sanitized.replace(tagRegex, '');
        
        return sanitized;
    },

    /**
     * Create element safely without innerHTML
     * @param {string} tagName - HTML tag name
     * @param {object} attributes - Element attributes
     * @param {string} textContent - Text content (not HTML)
     * @returns {HTMLElement} - Created element
     */
    createElement(tagName, attributes = {}, textContent = '') {
        const element = document.createElement(tagName);
        
        for (const [key, value] of Object.entries(attributes)) {
            if (key === 'className') {
                element.className = value;
            } else if (key.startsWith('data-')) {
                element.setAttribute(key, value);
            } else if (key !== 'innerHTML' && key !== 'outerHTML') {
                element.setAttribute(key, value);
            }
        }
        
        if (textContent) {
            element.textContent = textContent;
        }
        
        return element;
    },

    /**
     * Validate JSON input safely
     * @param {string} jsonString - JSON string to parse
     * @returns {object|null} - Parsed object or null on error
     */
    safeJSONParse(jsonString) {
        try {
            return JSON.parse(jsonString);
        } catch (e) {
            console.warn('Invalid JSON:', e.message);
            return null;
        }
    },

    /**
     * Validate URL to prevent SSRF attacks
     * @param {string} url - URL to validate
     * @returns {boolean} - True if valid and safe
     */
    isValidURL(url) {
        try {
            const parsed = new URL(url);
            const hostname = parsed.hostname.toLowerCase();
            
            // Block localhost and private IPs
            const blockedPatterns = [
                /^localhost$/,
                /^127\./,
                /^10\./,
                /^172\.(1[6-9]|2[0-9]|3[0-1])\./,
                /^192\.168\./,
                /^0\.0\.0\.0$/
            ];
            
            return !blockedPatterns.some(pattern => pattern.test(hostname));
        } catch {
            return false;
        }
    }
};

// Export for use in app.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SecurityUtils;
}
