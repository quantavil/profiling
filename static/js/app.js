/* Main Dashboard State Handler using Alpine.js */

function dashboardApp() {
    return {
        username: '',
        limit: 250,
        source: 'all',
        loading: false,
        error: null,
        profile: null,
        
        // History List
        savedProfiles: [],
        
        // Tabs
        subredditTab: 'combined',
        heatmapTab: 'combined',
        keywordTab: 'combined',
        
        // Reader filters and navigation
        readerTab: 'all',
        readerSort: 'newest',
        readerSearch: '',
        keywordFilter: null,
        readerPage: 1,
        readerPageSize: 10,
        expandedItems: [],
        
        // Performance Optimized State
        filteredItems: [],
        maxHeatmapVal: 0,
        
        // Dynamic Header UTC Clock
        currentUTC: '',
        
        // Loading Log State
        loadingStep: 'Initializing...',
        loadingInterval: null,
        loadingSeconds: 0,
        
        // Helpers
        weekdays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],

        init() {
            // Listen for hash changes
            window.addEventListener('hashchange', () => this.handleRoute());
            
            // Handle initial route on startup
            this.handleRoute();
            
            // Watchers
            this.$watch('subredditTab', (value) => {
                if (this.profile) {
                    updateSubredditChart(this.profile, value);
                }
            });
            this.$watch('profile', (value) => {
                if (value) {
                    this.$nextTick(() => {
                        updateSubredditChart(value, this.subredditTab);
                        lucide.createIcons();
                    });
                } else {
                    this.$nextTick(() => {
                        lucide.createIcons();
                    });
                }
                this.updateFilteredItems();
                this.updateMaxHeatmapVal();
            });
            this.$watch('heatmapTab', () => {
                this.updateMaxHeatmapVal();
            });
            
            // Watchers for filtering and pagination updates
            this.$watch('readerTab', () => { this.readerPage = 1; this.updateFilteredItems(); this.refreshIcons(); });
            this.$watch('readerSort', () => { this.readerPage = 1; this.updateFilteredItems(); this.refreshIcons(); });
            this.$watch('readerSearch', () => { this.readerPage = 1; this.updateFilteredItems(); this.refreshIcons(); });
            this.$watch('keywordFilter', () => { this.readerPage = 1; this.updateFilteredItems(); this.refreshIcons(); });
            this.$watch('readerPage', () => this.refreshIcons());
            
            // Initialize UTC time and update it every second
            this.updateUTC();
            setInterval(() => this.updateUTC(), 1000);
        },

        updateUTC() {
            const date = new Date();
            this.currentUTC = date.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        },

        getCurrentUTCDateTime() {
            return this.currentUTC;
        },

        handleRoute() {
            const hash = window.location.hash;
            if (hash.startsWith('#/user/')) {
                const name = decodeURIComponent(hash.replace('#/user/', ''));
                if (name && (!this.profile || (this.profile.queried_username !== name && this.profile.about?.name !== name))) {
                    this.loadSavedProfile(name);
                }
            } else {
                if (this.profile) {
                    this.profile = null;
                }
                // Only load saved profiles if they haven't been loaded yet to prevent redundant API calls
                if (this.savedProfiles.length === 0) {
                    this.loadSavedProfiles();
                }
            }
        },

        refreshIcons() {
            this.$nextTick(() => {
                lucide.createIcons();
            });
        },

        startLoadingLogs() {
            this.loadingSeconds = 0;
            this.loadingStep = `Fetching and analyzing public activity... (0s elapsed)`;
            this.loadingInterval = setInterval(() => {
                this.loadingSeconds++;
                this.loadingStep = `Fetching and analyzing public activity... (${this.loadingSeconds}s elapsed)`;
            }, 1000);
        },

        stopLoadingLogs() {
            if (this.loadingInterval) {
                clearInterval(this.loadingInterval);
                this.loadingInterval = null;
            }
        },

        async loadSavedProfiles() {
            try {
                const response = await fetch(`/api/profiles?t=${Date.now()}`);
                if (response.ok) {
                    this.savedProfiles = await response.json();
                }
            } catch (err) {
                console.error('Failed to load saved profiles:', err);
            } finally {
                this.refreshIcons();
            }
        },

        async loadSavedProfile(name) {
            this.loading = true;
            this.error = null;
            this.profile = null;
            this.expandedItems = [];
            this.keywordFilter = null;
            this.readerSearch = '';
            this.readerPage = 1;
            
            // Update URL hash to support page reloading
            const targetHash = `#/user/${encodeURIComponent(name)}`;
            if (window.location.hash !== targetHash) {
                window.location.hash = targetHash;
            }
            
            try {
                const response = await fetch(`/api/profiles/${encodeURIComponent(name)}?t=${Date.now()}`);
                const result = await response.json();
                
                if (!response.ok) {
                    throw new Error(result.detail || 'Failed to retrieve saved profile.');
                }
                
                this.profile = result;
            } catch (err) {
                console.error(err);
                this.error = err.message || 'Failed to load cached profile.';
            } finally {
                this.loading = false;
            }
        },

        async deleteProfile(name) {
            if (!confirm(`Are you sure you want to delete the saved profile for u/${name}?`)) {
                return;
            }
            
            try {
                const response = await fetch(`/api/profiles/${encodeURIComponent(name)}?t=${Date.now()}`, {
                    method: 'DELETE'
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.detail || 'Delete failed.');
                }
                
                // Reload list
                await this.loadSavedProfiles();
                
                // If current active profile is deleted, close it
                if (this.profile && (this.profile.queried_username === name || this.profile.about?.name === name)) {
                    this.profile = null;
                }
            } catch (err) {
                console.error(err);
                this.error = err.message || 'Failed to delete profile.';
            }
        },

        async reScrapeProfile(name) {
            this.username = name;
            await this.analyseUser();
        },

        closeActiveProfile() {
            window.location.hash = '#/';
        },

        async analyseUser() {
            if (!this.username) return;
            this.loading = true;
            this.error = null;
            this.profile = null;
            this.expandedItems = [];
            this.keywordFilter = null;
            this.readerSearch = '';
            this.readerPage = 1;
            
            this.startLoadingLogs();
            
            const url = `/api/analyse?username=${encodeURIComponent(this.username)}&limit=${this.limit}&source=${this.source}&t=${Date.now()}`;
            
            try {
                const response = await fetch(url);
                const result = await response.json();
                
                if (!response.ok) {
                    throw new Error(result.detail || 'An error occurred during fetch.');
                }
                
                this.profile = result;
                
                // Set the URL hash to save the page state on refresh
                const name = result.queried_username || result.about?.name;
                if (name) {
                    window.location.hash = `#/user/${encodeURIComponent(name)}`;
                }
                
                // Refresh history
                await this.loadSavedProfiles();
            } catch (err) {
                console.error(err);
                this.error = err.message || 'Server connection failed.';
            } finally {
                this.loading = false;
                this.stopLoadingLogs();
            }
        },

        setSubredditTab(tab) {
            this.subredditTab = tab;
        },

        setHeatmapTab(tab) {
            this.heatmapTab = tab;
        },

        setKeywordTab(tab) {
            this.keywordTab = tab;
        },

        // Heatmap Data Getter
        get activeHeatmapData() {
            if (!this.profile) return Array(7).fill(null).map(() => Array(24).fill(0));
            if (this.heatmapTab === 'posts') {
                return this.profile.heatmap_posts || Array(7).fill(null).map(() => Array(24).fill(0));
            } else if (this.heatmapTab === 'comments') {
                return this.profile.heatmap_comments || Array(7).fill(null).map(() => Array(24).fill(0));
            } else {
                return this.profile.heatmap_combined || Array(7).fill(null).map(() => Array(24).fill(0));
            }
        },

        updateMaxHeatmapVal() {
            const grid = this.activeHeatmapData;
            this.maxHeatmapVal = Math.max(...grid.flatMap(row => row), 0);
        },

        getCellStyle(count) {
            if (count === 0) {
                return 'background-color: rgba(35, 39, 49, 0.15); border: 1px solid rgba(35, 39, 49, 0.35);';
            }
            
            const ratio = this.maxHeatmapVal > 0 ? (count / this.maxHeatmapVal) : 0;
            // Opacity between 0.15 and 1.0
            const opacity = 0.15 + (0.85 * ratio);
            
            return `background-color: rgba(217, 119, 6, ${opacity}); border: 1px solid rgba(217, 119, 6, 0.3);`;
        },

        // Keywords Data Getter
        get activeKeywords() {
            if (!this.profile) return [];
            if (this.keywordTab === 'posts') {
                return this.profile.top_keywords_posts || [];
            } else if (this.keywordTab === 'comments') {
                return this.profile.top_keywords_comments || [];
            } else {
                return this.profile.top_keywords_combined || [];
            }
        },

        toggleKeywordFilter(word) {
            if (this.keywordFilter === word) {
                this.keywordFilter = null;
            } else {
                this.keywordFilter = word;
            }
        },

        clearAllFilters() {
            this.keywordFilter = null;
            this.readerSearch = '';
            this.readerTab = 'all';
            this.readerPage = 1;
        },

        // Contributions Reader Computing
        get totalAnalysisItems() {
            if (!this.profile) return 0;
            return (this.profile.posts_raw?.length || 0) + (this.profile.comments_raw?.length || 0);
        },

        updateFilteredItems() {
            if (!this.profile) {
                this.filteredItems = [];
                return;
            }
            
            let items = [];
            const posts = this.profile.posts_raw || [];
            const comments = this.profile.comments_raw || [];
            
            if (this.readerTab === 'posts') {
                items = [...posts];
            } else if (this.readerTab === 'comments') {
                items = [...comments];
            } else {
                items = [...posts, ...comments];
            }
            
            // Filter by keyword
            if (this.keywordFilter) {
                const kw = this.keywordFilter.toLowerCase();
                items = items.filter(item => {
                    const text = (item.title || '') + ' ' + (item.selftext || '') + ' ' + (item.body || '');
                    return text.toLowerCase().includes(kw);
                });
            }
            
            // Filter by reader search query
            if (this.readerSearch) {
                const q = this.readerSearch.toLowerCase();
                items = items.filter(item => {
                    const text = (item.title || '') + ' ' + (item.selftext || '') + ' ' + (item.body || '');
                    return text.toLowerCase().includes(q);
                });
            }
            
            // Sort items
            items.sort((a, b) => {
                let valA, valB;
                if (this.readerSort.includes('score')) {
                    valA = a.score ?? 0;
                    valB = b.score ?? 0;
                    return this.readerSort === 'highest_score' ? valB - valA : valA - valB;
                } else {
                    valA = a.created_utc ?? 0;
                    valB = b.created_utc ?? 0;
                    return this.readerSort === 'newest' ? valB - valA : valA - valB;
                }
            });
            
            this.filteredItems = items;
        },

        get paginatedItems() {
            const start = (this.readerPage - 1) * this.readerPageSize;
            return this.filteredItems.slice(start, start + this.readerPageSize);
        },

        get totalPages() {
            return Math.max(1, Math.ceil(this.filteredItems.length / this.readerPageSize));
        },

        prevPage() {
            if (this.readerPage > 1) {
                this.readerPage--;
            }
        },

        nextPage() {
            if (this.readerPage < this.totalPages) {
                this.readerPage++;
            }
        },

        setPage(p) {
            this.readerPage = p;
        },

        getPageNumbers() {
            const total = this.totalPages;
            const current = this.readerPage;
            const delta = 2;
            
            let pages = [];
            let start = Math.max(1, current - delta);
            let end = Math.min(total, current + delta);
            
            for (let i = start; i <= end; i++) {
                pages.push(i);
            }
            return pages;
        },

        // Expand/Collapse post details helpers
        getItemKey(item) {
            return item.name || (item.permalink + '-' + item.created_utc);
        },

        isItemExpanded(key) {
            return this.expandedItems.includes(key);
        },

        toggleExpandItem(key) {
            const idx = this.expandedItems.indexOf(key);
            if (idx > -1) {
                this.expandedItems.splice(idx, 1);
            } else {
                this.expandedItems.push(key);
            }
            this.refreshIcons();
        },

        hasBodyText(item) {
            return !!(item.body || item.selftext);
        },

        getItemText(item) {
            return item.body || item.selftext || '';
        },

        getBodyWordCount(item) {
            const text = this.getItemText(item);
            return text.split(/\s+/).filter(Boolean).length;
        },

        itemTextTooLong(item) {
            const text = this.getItemText(item);
            return text.length > 250;
        },

        getDisplayBody(item) {
            const text = this.getItemText(item);
            const key = this.getItemKey(item);
            if (this.itemTextTooLong(item) && !this.isItemExpanded(key)) {
                return text.slice(0, 240) + '...';
            }
            return text;
        },

        // Formatting Helpers
        formatNumber(val) {
            if (val === undefined || val === null) return '0';
            return Number(val).toLocaleString();
        },

        formatEpochDate(seconds) {
            if (!seconds) return '';
            return new Date(seconds * 1000).toISOString().split('T')[0];
        },

        formatEpochDateTime(seconds) {
            if (!seconds) return '';
            const date = new Date(seconds * 1000);
            return date.toISOString().replace('T', ' ').substring(0, 16) + ' UTC';
        },

        formatAccountAge(createdSeconds) {
            if (!createdSeconds) return '';
            const cake = new Date(createdSeconds * 1000);
            const diffMs = Date.now() - cake.getTime();
            const ageDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
            const years = (ageDays / 365).toFixed(1);
            return `${ageDays} days (~${years} years)`;
        },

        formatUTCOffset(offset) {
            if (offset === undefined || offset === null) return 'N/A';
            const sign = offset >= 0 ? '+' : '-';
            const absOffset = Math.abs(offset);
            const hours = Math.floor(absOffset);
            const minutes = Math.round((absOffset - hours) * 60);
            return `UTC${sign}${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
        },

        formatRelativeTime(epochSeconds) {
            if (!epochSeconds) return '';
            const diffMs = Date.now() - (epochSeconds * 1000);
            const diffSecs = Math.floor(diffMs / 1000);
            if (diffSecs < 60) return 'just now';
            const diffMins = Math.floor(diffSecs / 60);
            if (diffMins < 60) return `${diffMins}m ago`;
            const diffHours = Math.floor(diffMins / 60);
            if (diffHours < 24) return `${diffHours}h ago`;
            const diffDays = Math.floor(diffHours / 24);
            return `${diffDays}d ago`;
        }
    };
}
