
        };
        
        function switchCSP(csp) {
            // Update tabs
            document.querySelectorAll('.csp-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelector(`.csp-tab[data-csp="${csp}"]`).classList.add('active');
            
            // Update panels
            document.querySelectorAll('.content-panel').forEach(panel => panel.classList.remove('active'));
            document.getElementById(`panel-${csp}`).classList.add('active');
            
            // Update sidebar visibility
            document.querySelectorAll('.sidebar-section').forEach(section => {
                if (csp === 'all' || section.dataset.csp === csp) {
                    section.style.display = 'block';
                } else {
                    section.style.display = 'none';
                }
            });
            
            // Update table rows visibility
            document.querySelectorAll('.controls-table tr[data-csp]').forEach(row => {
                if (csp === 'all' || row.dataset.csp === csp) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        }
        
        function toggleSection(header) {
            header.parentElement.classList.toggle('expanded');
        }
        
        // Update stat widgets based on visible rows
        function updateStats() {
            const activePanel = document.querySelector('.content-panel.active');
            if (!activePanel) return;
            
            const visibleRows = activePanel.querySelectorAll('.controls-table tbody tr:not([style*="display: none"])');
            let total = 0, high = 0, medium = 0, low = 0;
            
            visibleRows.forEach(row => {
                total++;
                const crit = row.dataset.criticality || '';
                if (crit === 'high') high++;
                else if (crit === 'medium') medium++;
                else if (crit === 'low') low++;
            });
            
            // Update stat cards in active panel
            const stats = activePanel.querySelectorAll('.stat-card');
            stats.forEach(card => {
                const label = card.querySelector('.label')?.textContent.toLowerCase() || '';
                const numberEl = card.querySelector('.number');
                if (!numberEl) return;
                
                if (label.includes('total') || label.includes('controls')) {
                    numberEl.textContent = total;
                } else if (label.includes('high')) {
                    numberEl.textContent = high;
                } else if (label.includes('medium')) {
                    numberEl.textContent = medium;
                } else if (label.includes('low')) {
                    numberEl.textContent = low;
                }
            });
        }
        
        function showPolicyControls(csp, policyId) {
            // Highlight selected policy
            document.querySelectorAll('.policy-header').forEach(h => h.classList.remove('active'));
            const selectedPolicy = document.querySelector(`.policy-header[data-policy="${policyId}"]`);
            if (selectedPolicy) selectedPolicy.classList.add('active');
            
            // Switch to CSP tab
            switchCSP(csp);
            
            // Filter table to show only controls from this policy
            const activePanel = document.querySelector('.content-panel.active');
            if (!activePanel) return;
            
            // Get policy name from the selected policy header
            const policyName = selectedPolicy ? selectedPolicy.querySelector('.name').textContent : '';
            
            activePanel.querySelectorAll('.controls-table tbody tr').forEach(row => {
                const cid = row.querySelector('.cid')?.textContent.replace('CID-', '');
                const control = controlsData[csp]?.[cid];
                if (control && control.policyNames) {
                    const inPolicy = control.policyNames.some(p => p === policyName);
                    row.style.display = inPolicy ? '' : 'none';
                } else {
                    row.style.display = 'none';
                }
            });
            
            // Reset filter pills to "All" state visually but keep policy filter active
            activePanel.querySelectorAll('.filter-pill').forEach(pill => {
                pill.classList.remove('active');
            });
            
            // Update stats
            updateStats();
            
            showToast(`Showing controls for: ${policyName}`);
        }
        
        function showAllControls(csp) {
            // Reset policy selection
            document.querySelectorAll('.policy-header').forEach(h => h.classList.remove('active'));
            
            // Show all rows in active panel
            const activePanel = document.querySelector('.content-panel.active');
            if (!activePanel) return;
            
            activePanel.querySelectorAll('.controls-table tbody tr').forEach(row => {
                row.style.display = '';
            });
            
            // Reset filter pills
            activePanel.querySelectorAll('.filter-pill').forEach(pill => {
                pill.classList.toggle('active', pill.dataset.filter === 'all');
            });
            
            // Update stats
            updateStats();
            
            showToast('Showing all controls');
        }
        
        function showControlDetail(csp, cid) {
            const control = controlsData[csp]?.[cid];
            if (!control) return;
            
            document.getElementById('modalTitle').textContent = `CID-${cid}: ${control.controlName || 'Unknown'}`;
            
            const meta = document.getElementById('modalMeta');
            meta.innerHTML = `
                <span class="meta-item">☁️ ${csp}</span>
                <span class="meta-item">⚠️ ${control.criticality || 'N/A'}</span>
                <span class="meta-item">🔧 ${control.controlType || 'N/A'}</span>
                <span class="meta-item">📦 ${control.serviceType || 'N/A'}</span>
            `;
            
            let bodyHtml = `
                <div class="field-grid">
                    <div class="field">
                        <div class="field-label">Control ID</div>
                        <div class="field-value">${cid}</div>
                    </div>
                    <div class="field">
                        <div class="field-label">Criticality</div>
                        <div class="field-value ${(control.criticality || '').toLowerCase()}">${control.criticality || 'N/A'}</div>
                    </div>
                    <div class="field">
                        <div class="field-label">Control Type</div>
                        <div class="field-value">${control.controlType || 'N/A'}</div>
                    </div>
                    <div class="field">
                        <div class="field-label">Cloud Provider</div>
                        <div class="field-value">${csp}</div>
                    </div>
                    <div class="field">
                        <div class="field-label">Service Type</div>
                        <div class="field-value">${control.serviceType || 'N/A'}</div>
                    </div>
                    <div class="field">
                        <div class="field-label">Resource Type</div>
                        <div class="field-value">${control.resourceType || 'N/A'}</div>
                    </div>
                </div>
            `;
            
            if (control.rationale) {
                bodyHtml += `
                    <div class="field" style="margin-bottom:20px;">
                        <div class="field-label">Rationale</div>
                        <div class="field-value">${control.rationale}</div>
                    </div>
                `;
            }
            
            if (control.manualRemediation) {
                bodyHtml += `
                    <div class="remediation manual">
                        <h4>🔧 Manual Remediation</h4>
                        <div class="content">${control.manualRemediation}</div>
                    </div>
                `;
            }
            
            if (control.cliRemediation) {
                bodyHtml += `
                    <div class="remediation cli" style="margin-top:15px;">
                        <h4>💻 CLI Remediation</h4>
                        <div class="content">${control.cliRemediation}</div>
                    </div>
                `;
            }
            
            document.getElementById('modalBody').innerHTML = bodyHtml;
            document.getElementById('modalOverlay').classList.add('active');
        }
        
        function closeModal(event) {
            if (!event || event.target === document.getElementById('modalOverlay')) {
                document.getElementById('modalOverlay').classList.remove('active');
            }
        }
        
        function globalFilter() {
            const input = document.getElementById('globalSearch').value.toLowerCase();
            // Only filter rows in the active panel
            const activePanel = document.querySelector('.content-panel.active');
            if (!activePanel) return;
            
            activePanel.querySelectorAll('.controls-table tbody tr').forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(input) ? '' : 'none';
            });
            
            // Update stats
            updateStats();
        }
        
        // Close modal on Escape and keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
            
            // Don't trigger shortcuts when typing in search
            if (e.target.tagName === 'INPUT') return;
            
            // Keyboard shortcuts
            switch(e.key.toLowerCase()) {
                case 'd': toggleTheme(); break;
                case 'e': exportCSV(); break;
                case 'p': window.print(); break;
                case '/': 
                    e.preventDefault();
                    document.getElementById('globalSearch').focus();
                    break;
                case '1': filterByCriticality('all'); break;
                case '2': filterByCriticality('high'); break;
                case '3': filterByCriticality('medium'); break;
                case '4': filterByCriticality('low'); break;
            }
        });
        
        // Theme toggle
        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', newTheme);
            
            const icon = document.getElementById('themeIcon');
            const btn = document.querySelector('.theme-toggle span:nth-child(2)');
            if (newTheme === 'dark') {
                icon.textContent = '☀️';
                btn.textContent = 'Light';
            } else {
                icon.textContent = '🌙';
                btn.textContent = 'Dark';
            }
            
            // Save preference
            localStorage.setItem('cspm-theme', newTheme);
            showToast(`Switched to ${newTheme} mode`);
        }
        
        // Load saved theme
        const savedTheme = localStorage.getItem('cspm-theme');
        if (savedTheme) {
            document.documentElement.setAttribute('data-theme', savedTheme);
            if (savedTheme === 'dark') {
                document.getElementById('themeIcon').textContent = '☀️';
                document.querySelector('.theme-toggle span:nth-child(2)').textContent = 'Light';
            }
        }
        
        // Filter by criticality
        function filterByCriticality(level) {
            document.querySelectorAll('.filter-pill').forEach(pill => {
                pill.classList.toggle('active', pill.dataset.filter === level);
            });
            
            // Only filter rows in the active panel
            const activePanel = document.querySelector('.content-panel.active');
            if (!activePanel) return;
            
            activePanel.querySelectorAll('.controls-table tbody tr').forEach(row => {
                if (level === 'all') {
                    row.style.display = '';
                } else {
                    const rowLevel = row.dataset.criticality || '';
                    row.style.display = rowLevel === level ? '' : 'none';
                }
            });
            
            // Update stats
            updateStats();
            
            showToast(`Filtered by: ${level === 'all' ? 'All' : level.charAt(0).toUpperCase() + level.slice(1)}`);
        }
        
        // Sort table
        let sortDirection = {};
        function sortTable(columnIndex) {
            const table = document.getElementById('controlsTable');
            if (!table) return;
            
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            sortDirection[columnIndex] = !sortDirection[columnIndex];
            const dir = sortDirection[columnIndex] ? 1 : -1;
            
            rows.sort((a, b) => {
                const aVal = a.cells[columnIndex]?.textContent.trim() || '';
                const bVal = b.cells[columnIndex]?.textContent.trim() || '';
                return aVal.localeCompare(bVal, undefined, {numeric: true}) * dir;
            });
            
            rows.forEach(row => tbody.appendChild(row));
            
            // Update sort indicators
            table.querySelectorAll('.sort-indicator').forEach((ind, i) => {
                ind.textContent = i === columnIndex ? (sortDirection[columnIndex] ? '↑' : '↓') : '↕';
                ind.classList.toggle('active', i === columnIndex);
            });
        }
        
        // Export to CSV
        function exportCSV() {
            const table = document.getElementById('controlsTable');
            if (!table) return;
            
            let csv = [];
            const headers = Array.from(table.querySelectorAll('th')).map(th => 
                th.textContent.replace(/[↕↑↓]/g, '').trim()
            );
            csv.push(headers.join(','));
            
            table.querySelectorAll('tbody tr').forEach(row => {
                if (row.style.display !== 'none') {
                    const cells = Array.from(row.querySelectorAll('td')).map(td => 
                        '"' + td.textContent.trim().replace(/"/g, '""') + '"'
                    );
                    csv.push(cells.join(','));
                }
            });
            
            const blob = new Blob([csv.join('\n')], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'cspm_controls_' + new Date().toISOString().slice(0,10) + '.csv';
            a.click();
            URL.revokeObjectURL(url);
            
            showToast('CSV exported successfully!');
        }
        
        // Toast notification
        function showToast(message) {
            let toast = document.getElementById('toast');
            if (!toast) {
                toast = document.createElement('div');
                toast.id = 'toast';
                toast.className = 'toast';
                document.body.appendChild(toast);
            }
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 2500);
        }
        
        // Copy to clipboard
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('Copied to clipboard!');
            });
        }
    </script>
</body>
</html>
