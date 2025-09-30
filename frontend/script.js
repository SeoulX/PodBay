// API Configuration
const API_BASE_URL = 'http://localhost:8000/api/v1';

// Global state
let currentContext = '';
let refreshInterval = null;

// Cache for data persistence
const dataCache = {
    contexts: null,
    pods: null,
    nodes: null,
    clusterSummary: null,
    podMetrics: null,
    nodeMetrics: null,
    lastUpdated: {}
};

// Cache TTL (Time To Live) in milliseconds
const CACHE_TTL = {
    contexts: 300000,    // 5 minutes
    pods: 30000,         // 30 seconds
    nodes: 60000,        // 1 minute
    clusterSummary: 30000, // 30 seconds
    podMetrics: 30000,   // 30 seconds
    nodeMetrics: 30000   // 30 seconds
};

// DOM Elements
const contextSelect = document.getElementById('contextSelect');
const loadingOverlay = document.getElementById('loadingOverlay');
const metricsGrid = document.getElementById('metricsGrid');
const podsTable = document.getElementById('podsTable');
const nodesTable = document.getElementById('nodesTable');

// Cache Management
function isCacheValid(key) {
    if (!dataCache[key] || !dataCache.lastUpdated[key]) {
        return false;
    }
    const now = Date.now();
    const lastUpdated = dataCache.lastUpdated[key];
    const ttl = CACHE_TTL[key] || 30000;
    return (now - lastUpdated) < ttl;
}

function setCache(key, data) {
    dataCache[key] = data;
    dataCache.lastUpdated[key] = Date.now();
}

function getCache(key) {
    return dataCache[key];
}

function clearCache(key) {
    if (key) {
        dataCache[key] = null;
        delete dataCache.lastUpdated[key];
    } else {
        // Clear all cache
        Object.keys(dataCache).forEach(k => {
            if (k !== 'lastUpdated') {
                dataCache[k] = null;
            }
        });
        dataCache.lastUpdated = {};
    }
}

// Utility Functions
function showLoading(message = 'Loading data...') {
    const loadingText = document.getElementById('loadingText');
    if (loadingText) {
        loadingText.textContent = message;
    }
    loadingOverlay.classList.add('show');
}

function hideLoading() {
    loadingOverlay.classList.remove('show');
}

// Add a timeout to hide loading after maximum time
function showLoadingWithTimeout(timeoutMs = 30000) {
    showLoading('Initializing...');
    setTimeout(() => {
        hideLoading();
        console.warn('Loading timeout reached, hiding loading indicator');
    }, timeoutMs);
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatCpu(millicores) {
    if (millicores >= 1000) {
        return (millicores / 1000).toFixed(1) + ' cores';
    }
    return millicores.toFixed(0) + 'm';
}

function getStatusClass(status) {
    const normalizedStatus = status.toLowerCase();
    if (normalizedStatus.includes('running') || normalizedStatus.includes('ready')) {
        return 'status-running';
    } else if (normalizedStatus.includes('pending') || normalizedStatus.includes('waiting')) {
        return 'status-pending';
    } else if (normalizedStatus.includes('failed') || normalizedStatus.includes('error')) {
        return 'status-failed';
    } else {
        return 'status-unknown';
    }
}

// API Functions
async function apiCall(endpoint, options = {}) {
    try {
        console.log(`Making API call to: ${API_BASE_URL}${endpoint}`);
        
        // Add timeout to prevent hanging
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
        
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            signal: controller.signal,
            ...options
        });
        
        clearTimeout(timeoutId);
        console.log(`Response status: ${response.status}`);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error(`HTTP error! status: ${response.status}, body: ${errorText}`);
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('API response received');
        return data;
    } catch (error) {
        if (error.name === 'AbortError') {
            console.error('API call timed out:', endpoint);
            throw new Error('Request timed out');
        }
        console.error('API call failed:', error);
        throw error;
    }
}

async function loadContexts(forceRefresh = false) {
    try {
        // Check cache first
        if (!forceRefresh && isCacheValid('contexts')) {
            console.log('Using cached contexts data');
            const data = getCache('contexts');
            updateContextSelector(data);
            return data;
        }

        console.log('Loading contexts from API...');
        const data = await apiCall('/contexts');
        currentContext = data.current_context;
        
        // Update cache
        setCache('contexts', data);
        
        // Update UI
        updateContextSelector(data);
        
        return data;
    } catch (error) {
        console.error('Failed to load contexts:', error);
        contextSelect.innerHTML = '<option value="">Error loading contexts</option>';
        return null;
    }
}

function updateContextSelector(data) {
    contextSelect.innerHTML = '';
    data.contexts.forEach(context => {
        const option = document.createElement('option');
        option.value = context.name;
        option.textContent = context.name;
        if (context.name === data.current_context) {
            option.selected = true;
        }
        contextSelect.appendChild(option);
    });
}

async function loadClusterSummary(forceRefresh = false) {
    try {
        // Check cache first
        if (!forceRefresh && isCacheValid('clusterSummary')) {
            console.log('Using cached cluster summary data');
            const data = getCache('clusterSummary');
            updateClusterSummaryUI(data);
            return data;
        }

        console.log('Loading cluster summary from API...');
        const params = currentContext ? `?context=${encodeURIComponent(currentContext)}` : '';
        const data = await apiCall(`/monitoring/summary${params}`);
        
        // Update cache
        setCache('clusterSummary', data);
        
        // Update UI
        updateClusterSummaryUI(data);
            
        return data;
    } catch (error) {
        console.error('Failed to load cluster summary:', error);
        // Fallback: show basic info without metrics
        updateClusterSummaryUI(null);
        return null;
    }
}

function updateClusterSummaryUI(data) {
    if (data) {
        // Update metrics
        document.getElementById('nodeCount').textContent = data.node_count || 0;
        document.getElementById('podCount').textContent = data.pod_count || 0;
        document.getElementById('cpuUsage').textContent = `${(data.cpu_usage_percentage || 0).toFixed(1)}%`;
        document.getElementById('memoryUsage').textContent = `${(data.memory_usage_percentage || 0).toFixed(1)}%`;
        
        document.getElementById('cpuDetails').textContent = 
            `${formatCpu(data.cpu_usage_millicores || 0)} / ${formatCpu(data.cpu_capacity_millicores || 0)}`;
        document.getElementById('memoryDetails').textContent = 
            `${(data.memory_usage_mib || 0).toFixed(0)}Mi / ${(data.memory_capacity_mib || 0).toFixed(0)}Mi`;
    } else {
        // Show fallback data
        document.getElementById('nodeCount').textContent = '-';
        document.getElementById('podCount').textContent = '-';
        document.getElementById('cpuUsage').textContent = 'N/A';
        document.getElementById('memoryUsage').textContent = 'N/A';
        document.getElementById('cpuDetails').textContent = 'Metrics server not available';
        document.getElementById('memoryDetails').textContent = 'Metrics server not available';
    }
}

async function loadPods(forceRefresh = false) {
    try {
        // Check cache first
        if (!forceRefresh && isCacheValid('pods')) {
            console.log('Using cached pods data');
            const data = getCache('pods');
            updatePodsUI(data);
            return data;
        }

        console.log('Loading pods from API...');
        const data = await apiCall('/pods');
        
        // Update cache
        setCache('pods', data);
        
        // Update UI
        updatePodsUI(data);
        
        return data;
    } catch (error) {
        console.error('Failed to load pods:', error);
        podsTable.innerHTML = '<tr><td colspan="4" class="loading">Error loading pods</td></tr>';
        return null;
    }
}

function updatePodsUI(data) {
    // Count running pods
    const runningPods = data.filter(pod => 
        pod.status.toLowerCase().includes('running')
    ).length;
    
    document.getElementById('runningPods').textContent = `${runningPods} running`;
    
    // Update pods table
    podsTable.innerHTML = '';
    if (data.length === 0) {
        podsTable.innerHTML = '<tr><td colspan="4" class="loading">No pods found</td></tr>';
    } else {
        data.slice(0, 10).forEach(pod => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${pod.name}</td>
                <td>${pod.namespace}</td>
                <td><span class="status-badge ${getStatusClass(pod.status)}">${pod.status}</span></td>
                <td>${pod.node || '-'}</td>
            `;
            podsTable.appendChild(row);
        });
    }
}

async function loadNodes(forceRefresh = false) {
    try {
        // Check cache first
        if (!forceRefresh && isCacheValid('nodes')) {
            console.log('Using cached nodes data');
            const data = getCache('nodes');
            updateNodesUI(data);
            return data;
        }

        console.log('Loading nodes from API...');
        const data = await apiCall('/nodes');
        
        // Update cache
        setCache('nodes', data);
        
        // Update UI
        updateNodesUI(data);
        
        return data;
    } catch (error) {
        console.error('Failed to load nodes:', error);
        nodesTable.innerHTML = '<tr><td colspan="4" class="loading">Error loading nodes</td></tr>';
        return null;
    }
}

function updateNodesUI(data) {
    // Update nodes table
    nodesTable.innerHTML = '';
    if (data.length === 0) {
        nodesTable.innerHTML = '<tr><td colspan="4" class="loading">No nodes found</td></tr>';
    } else {
        data.forEach(node => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${node.name}</td>
                <td>${node.cpu || '-'}</td>
                <td>${node.memory || '-'}</td>
                <td><span class="status-badge status-running">Ready</span></td>
            `;
            nodesTable.appendChild(row);
        });
    }
}

// Main Functions
async function refreshData() {
    showLoading('Loading pods and nodes...');
    
    try {
        console.log('Refreshing dashboard data...');
        
        // Load basic data first (faster)
        const [podsData, nodesData] = await Promise.all([
            loadPods(),
            loadNodes()
        ]);
        
        showLoading('Loading monitoring data...');
        
        // Then load monitoring data (slower)
        try {
            await loadClusterSummary();
        } catch (error) {
            console.warn('Monitoring data not available:', error);
            // Show fallback data
            document.getElementById('nodeCount').textContent = nodesData?.length || 0;
            document.getElementById('podCount').textContent = podsData?.length || 0;
            document.getElementById('cpuUsage').textContent = 'N/A';
            document.getElementById('memoryUsage').textContent = 'N/A';
            document.getElementById('cpuDetails').textContent = 'Metrics server not available';
            document.getElementById('memoryDetails').textContent = 'Metrics server not available';
        }
        
        console.log('Dashboard data refreshed successfully');
    } catch (error) {
        console.error('Failed to refresh data:', error);
        // Show error state
        document.getElementById('metricsGrid').innerHTML = '<div class="metric-card"><div class="metric-content"><h3>Error</h3><div class="metric-value">Failed to load data</div><div class="metric-subtitle">Check console for details</div></div></div>';
    } finally {
        hideLoading();
    }
}

async function switchContext(contextName) {
    if (!contextName) return;
    
    showLoading();
    
    try {
        await apiCall(`/contexts/${encodeURIComponent(contextName)}/switch`, {
            method: 'POST'
        });
        
        currentContext = contextName;
        await refreshData();
    } catch (error) {
        console.error('Failed to switch context:', error);
        alert('Failed to switch context. Please try again.');
    } finally {
        hideLoading();
    }
}

// Event Listeners
contextSelect.addEventListener('change', (e) => {
    if (e.target.value !== currentContext) {
        switchContext(e.target.value);
    }
});

// Panel Management
function showPanel(panelId) {
    // Hide all panels
    document.querySelectorAll('.panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    // Show selected panel
    const panel = document.getElementById(panelId);
    if (panel) {
        panel.classList.add('active');
    }
}

function updatePageTitle(title) {
    document.querySelector('.page-title').textContent = title;
}

// Navigation
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        
        // Remove active class from all items
        document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
        
        // Add active class to clicked item
        item.classList.add('active');
        
        // Get panel ID from data-page attribute
        const page = item.getAttribute('data-page');
        const panelId = page + 'Panel';
        
        // Show corresponding panel
        showPanel(panelId);
        
        // Update page title
        const pageTitle = item.querySelector('span').textContent;
        updatePageTitle(pageTitle);
        
        // Load data for the panel
        loadPanelData(page);
    });
});

// Initialize App
async function init() {
    showLoadingWithTimeout(30000); // 30 second max loading time
    
    try {
        console.log('Initializing app...');
        
        // Wait a bit for backend to be ready
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Load contexts first
        console.log('Loading contexts...');
        await loadContexts();
        
        // Wait a bit for context to be set
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Then load all data
        console.log('Refreshing data...');
        await refreshData();
        
        // Set up auto-refresh every 60 seconds (less frequent)
        refreshInterval = setInterval(refreshData, 60000);
        
        console.log('App initialized successfully');
    } catch (error) {
        console.error('Failed to initialize app:', error);
        // Show error message to user
        document.getElementById('metricsGrid').innerHTML = '<div class="metric-card"><div class="metric-content"><h3>Error</h3><div class="metric-value">Failed to load data</div><div class="metric-subtitle">Check console for details</div></div></div>';
    } finally {
        hideLoading();
    }
}

// Panel Data Loading
async function loadPanelData(page) {
    switch (page) {
        case 'dashboard':
            await refreshData();
            break;
        case 'pods':
            await loadAllPods();
            break;
        case 'nodes':
            await loadAllNodes();
            break;
        case 'monitoring':
            await loadMonitoringData();
            break;
        case 'contexts':
            await loadContextsData();
            break;
    }
}

// Pods Panel Functions
async function loadAllPods() {
    try {
        const data = await apiCall('/pods');
        const table = document.getElementById('allPodsTable');
        
        table.innerHTML = '';
        if (data.length === 0) {
            table.innerHTML = '<tr><td colspan="5" class="loading">No pods found</td></tr>';
        } else {
            data.forEach(pod => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${pod.name}</td>
                    <td>${pod.namespace}</td>
                    <td><span class="status-badge ${getStatusClass(pod.status)}">${pod.status}</span></td>
                    <td>${pod.node || '-'}</td>
                    <td>-</td>
                `;
                table.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Failed to load pods:', error);
        document.getElementById('allPodsTable').innerHTML = '<tr><td colspan="5" class="loading">Error loading pods</td></tr>';
    }
}

async function refreshPods() {
    showLoading();
    try {
        await loadAllPods();
    } finally {
        hideLoading();
    }
}

// Nodes Panel Functions
async function loadAllNodes() {
    try {
        const data = await apiCall('/nodes');
        const table = document.getElementById('allNodesTable');
        
        table.innerHTML = '';
        if (data.length === 0) {
            table.innerHTML = '<tr><td colspan="5" class="loading">No nodes found</td></tr>';
        } else {
            data.forEach(node => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${node.name}</td>
                    <td>${node.cpu || '-'}</td>
                    <td>${node.memory || '-'}</td>
                    <td><span class="status-badge status-running">Ready</span></td>
                    <td>-</td>
                `;
                table.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Failed to load nodes:', error);
        document.getElementById('allNodesTable').innerHTML = '<tr><td colspan="5" class="loading">Error loading nodes</td></tr>';
    }
}

async function refreshNodes() {
    showLoading();
    try {
        await loadAllNodes();
    } finally {
        hideLoading();
    }
}

// Monitoring Panel Functions
async function loadMonitoringData() {
    try {
        // Load pod metrics
        const podMetrics = await apiCall('/monitoring/pods');
        const podTable = document.getElementById('podMetricsTable');
        
        podTable.innerHTML = '';
        if (podMetrics.length === 0) {
            podTable.innerHTML = '<tr><td colspan="5" class="loading">No pod metrics available</td></tr>';
        } else {
            podMetrics.forEach(pod => {
                pod.containers.forEach(container => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${pod.name}</td>
                        <td>${pod.namespace}</td>
                        <td>${container.name}</td>
                        <td>${container.cpu_usage_millicores.toFixed(1)}m</td>
                        <td>${container.memory_usage_mib.toFixed(1)}Mi</td>
                    `;
                    podTable.appendChild(row);
                });
            });
        }
        
        // Load node metrics
        const nodeMetrics = await apiCall('/monitoring/nodes');
        const nodeTable = document.getElementById('nodeMetricsTable');
        
        nodeTable.innerHTML = '';
        if (nodeMetrics.length === 0) {
            nodeTable.innerHTML = '<tr><td colspan="6" class="loading">No node metrics available</td></tr>';
        } else {
            nodeMetrics.forEach(node => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${node.name}</td>
                    <td>${node.cpu_usage_percentage.toFixed(1)}%</td>
                    <td>${node.cpu_capacity_cores} cores</td>
                    <td>${node.memory_usage_percentage.toFixed(1)}%</td>
                    <td>${node.memory_capacity_mib.toFixed(0)}Mi</td>
                    <td><span class="status-badge ${getStatusClass(node.status)}">${node.status}</span></td>
                `;
                nodeTable.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Failed to load monitoring data:', error);
        document.getElementById('podMetricsTable').innerHTML = '<tr><td colspan="5" class="loading">Error loading pod metrics</td></tr>';
        document.getElementById('nodeMetricsTable').innerHTML = '<tr><td colspan="6" class="loading">Error loading node metrics</td></tr>';
    }
}

async function refreshMonitoring() {
    showLoading();
    try {
        await loadMonitoringData();
    } finally {
        hideLoading();
    }
}

// Contexts Panel Functions
async function loadContextsData() {
    try {
        const data = await apiCall('/contexts');
        const table = document.getElementById('contextsTable');
        
        table.innerHTML = '';
        if (data.contexts.length === 0) {
            table.innerHTML = '<tr><td colspan="6" class="loading">No contexts found</td></tr>';
        } else {
            data.contexts.forEach(context => {
                const row = document.createElement('tr');
                const isCurrent = context.name === data.current_context;
                row.innerHTML = `
                    <td>${context.name}</td>
                    <td>${context.cluster}</td>
                    <td>${context.user}</td>
                    <td>${context.namespace}</td>
                    <td><span class="status-badge ${isCurrent ? 'status-running' : 'status-unknown'}">${isCurrent ? 'Active' : 'Inactive'}</span></td>
                    <td>
                        ${!isCurrent ? `<button class="btn btn-primary" onclick="switchContext('${context.name}')">Switch</button>` : 'Current'}
                    </td>
                `;
                table.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Failed to load contexts:', error);
        document.getElementById('contextsTable').innerHTML = '<tr><td colspan="6" class="loading">Error loading contexts</td></tr>';
    }
}

async function refreshContexts() {
    showLoading();
    try {
        await loadContextsData();
    } finally {
        hideLoading();
    }
}

// Global refresh function for button
window.refreshData = refreshData;
window.refreshPods = refreshPods;
window.refreshNodes = refreshNodes;
window.refreshMonitoring = refreshMonitoring;
window.refreshContexts = refreshContexts;

// Start the app when DOM is loaded
document.addEventListener('DOMContentLoaded', init);

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});
