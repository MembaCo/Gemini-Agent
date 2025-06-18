// dashboard/static/js/dashboard.js
// @author: Memba Co.

document.addEventListener('DOMContentLoaded', function () {
    const socket = io();
    let pnlChart;
    let currentOpportunity = null;

    // Element referansları
    const elements = {
        totalPnl: document.getElementById('total-pnl'),
        winRate: document.getElementById('win-rate'),
        totalTrades: document.getElementById('total-trades'),
        openPositionsContainer: document.getElementById('open-positions-container'),
        tradeHistoryContainer: document.getElementById('trade-history-container'),
        pnlChartCanvas: document.getElementById('pnlChart'),
        analysisForm: document.getElementById('analysis-form'),
        analysisBtn: document.getElementById('analysis-btn'),
        analysisStatus: document.getElementById('analysis-status'),
        scanBtn: document.getElementById('scan-btn'),
        scanStatusContainer: document.getElementById('scan-status-container'),
        opportunityModal: document.getElementById('opportunity-modal'),
        opportunityDetails: document.getElementById('opportunity-details'),
        confirmOpportunityBtn: document.getElementById('confirm-opportunity-btn'),
        cancelOpportunityBtn: document.getElementById('cancel-opportunity-btn'),
        reanalysisModal: document.getElementById('reanalysis-modal'),
        reanalysisDetails: document.getElementById('reanalysis-details'),
        reanalysisActions: document.getElementById('reanalysis-actions'),
        toastContainer: document.getElementById('toast-container')
    };

    // --- WebSocket Olay Dinleyicileri ---
    socket.on('connect', () => {
        console.log('Sunucuya bağlandı!');
        elements.scanStatusContainer.textContent = 'Sunucuya bağlanıldı. Veriler bekleniyor...';
        socket.emit('request_dashboard_data');
    });

    socket.on('disconnect', () => {
        console.log('Sunucu bağlantısı kesildi!');
        showToast('Sunucu bağlantısı kesildi. Sayfayı yenileyin.', 'error');
    });

    socket.on('dashboard_data', (data) => {
        updateDashboard(data);
    });

    socket.on('scan_status', (data) => {
        elements.scanStatusContainer.innerHTML = `<p>${data.message}</p>`;
        if (data.message.includes('Tamamlandı') || data.message.includes('Başlatılıyor') || data.message.includes('bekleniyor')) {
            elements.scanBtn.disabled = false;
        } else {
            elements.scanBtn.disabled = true;
        }
    });

    socket.on('new_opportunity', (opportunity) => {
        currentOpportunity = opportunity;
        showOpportunityModal(opportunity);
    });
    
    socket.on('reanalysis_result', (result) => {
        if (result.status === 'success') {
            showReanalysisModal(result.data);
        } else {
            showToast(`Analiz başarısız: ${result.message}`, 'error');
        }
    });

    socket.on('toast', (data) => {
        showToast(data.message, data.type);
    });

    // --- Olay Yönlendiricileri (Event Handlers) ---
    elements.analysisForm.addEventListener('submit', handleAnalysisFormSubmit);
    
    elements.scanBtn.addEventListener('click', () => {
        elements.scanBtn.disabled = true;
        elements.scanStatusContainer.textContent = 'Tarama başlatılıyor...';
        socket.emit('start_scan');
    });

    elements.openPositionsContainer.addEventListener('click', function(e) {
        const button = e.target.closest('button[data-action]');
        if (!button) return;
    
        const symbol = button.dataset.symbol;
        const action = button.dataset.action;
    
        if (action === 'close') {
            handleClosePosition(symbol); // Varsayılan olarak onay sorar
        } else if (action === 'reanalyze') {
            handleReanalyzePosition(symbol);
        }
    });
    
    elements.confirmOpportunityBtn.addEventListener('click', handleConfirmOpportunity);
    elements.cancelOpportunityBtn.addEventListener('click', hideOpportunityModal);

    // --- Arayüz Güncelleme Fonksiyonları ---
    function updateDashboard(data) {
        if (!data) return;
        
        const pnlValue = parseFloat(data.stats.total_pnl.replace(',', ''));
        elements.totalPnl.textContent = `${data.stats.total_pnl} USDT`;
        elements.totalPnl.className = `mt-1 text-3xl font-semibold ${pnlValue >= 0 ? 'positive-pnl' : 'negative-pnl'}`;
        elements.winRate.textContent = `${data.stats.win_rate}%`;
        elements.totalTrades.textContent = data.stats.total_trades;

        renderOpenPositions(data.open_positions);
        renderTradeHistory(data.trade_history);
        updateChart(data.pnl_timeline);
    }
    
    function renderOpenPositions(positions) {
        if (!positions || positions.length === 0) {
            elements.openPositionsContainer.innerHTML = '<p class="text-center text-slate-400">Yönetilen açık pozisyon bulunmuyor.</p>'; return;
        }
        elements.openPositionsContainer.innerHTML = `<table class="min-w-full divide-y divide-slate-700">
            <thead class="table-header"><tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Sembol</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Yön</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Anlık PNL</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">İşlemler</th>
            </tr></thead>
            <tbody class="divide-y divide-slate-700">${positions.map(p => `
                <tr>
                    <td class="px-4 py-4 whitespace-nowrap text-sm font-medium text-white">${p.symbol}</td>
                    <td class="px-4 py-4 whitespace-nowrap text-sm ${p.side === 'buy' ? 'positive-pnl' : 'negative-pnl'}">${p.side.toUpperCase()}</td>
                    <td class="px-4 py-4 whitespace-nowrap text-sm ${p.unrealizedPnl >= 0 ? 'positive-pnl' : 'negative-pnl'}">${p.unrealizedPnl.toFixed(2)} USDT</td>
                    <td class="px-4 py-4 whitespace-nowrap text-sm flex gap-2">
                        <button class="btn btn-blue text-xs" data-symbol="${p.symbol}" data-action="reanalyze">Analiz</button>
                        <button class="btn btn-red text-xs" data-symbol="${p.symbol}" data-action="close">Kapat</button>
                    </td>
                </tr>`).join('')}
            </tbody></table>`;
    }

    function renderTradeHistory(history) {
        if (!history || history.length === 0) {
            elements.tradeHistoryContainer.innerHTML = '<p class="text-center text-slate-400">Henüz tamamlanmış işlem bulunmuyor.</p>'; return;
        }
        elements.tradeHistoryContainer.innerHTML = `<table class="min-w-full divide-y divide-slate-700"><thead class="table-header"><tr>
            <th class="px-4 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Sembol</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">P&L</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Durum</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Zaman</th></tr></thead>
            <tbody class="divide-y divide-slate-700">${history.map(trade => `<tr>
                <td class="px-4 py-4 whitespace-nowrap text-sm font-medium text-white">${trade.symbol}</td>
                <td class="px-4 py-4 whitespace-nowrap text-sm ${trade.pnl >= 0 ? 'positive-pnl' : 'negative-pnl'}">${trade.pnl.toFixed(2)}</td>
                <td class="px-4 py-4 whitespace-nowrap text-sm text-slate-300">${trade.status}</td>
                <td class="px-4 py-4 whitespace-nowrap text-sm text-slate-300">${new Date(trade.closed_at).toLocaleString()}</td></tr>`).join('')}
            </tbody></table>`;
    }

    function updateChart(timelineData) {
        if (pnlChart) pnlChart.destroy();
        const ctx = elements.pnlChartCanvas.getContext('2d');
        pnlChart = new Chart(ctx, { type: 'line', data: { datasets: [{
                label: 'Kümülatif P&L (USDT)', data: timelineData,
                borderColor: 'rgb(59, 130, 246)', backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2.5, tension: 0.4, fill: true, pointRadius: 2, pointBackgroundColor: 'rgb(59, 130, 246)'
            }]}, options: { responsive: true, maintainAspectRatio: false, scales: {
                x: { type: 'time', time: { unit: 'day' }, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(51, 65, 85, 0.5)' } },
                y: { beginAtZero: false, ticks: { color: '#94a3b8', callback: v => v + ' $' }, grid: { color: 'rgba(51, 65, 85, 0.5)' } }
            }, plugins: { legend: { labels: { color: '#e2e8f0' } } } } });
    }

    // --- Yardımcı Fonksiyonlar ---
    async function handleClosePosition(symbol, skip_confirmation = false) {
        if (!skip_confirmation && !confirm(`${symbol} pozisyonunu kapatmak istediğinizden emin misiniz?`)) {
            return;
        }
        try {
            const response = await fetch('/api/close-position', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ symbol }) 
            });
            const result = await response.json();
            showToast(result.message, result.status);
        } catch (error) { 
            showToast('Pozisyon kapatılırken bir ağ hatası oluştu.', 'error'); 
        }
    }

    function handleReanalyzePosition(symbol) {
        socket.emit('reanalyze_position', { symbol: symbol });
    }

    async function handleAnalysisFormSubmit(e) {
        e.preventDefault();
        elements.analysisBtn.disabled = true;
        elements.analysisStatus.textContent = 'Analiz ediliyor... Lütfen bekleyin.';
        elements.analysisStatus.className = 'mt-4 text-sm text-slate-400';
        try {
            const response = await fetch('/api/new-analysis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: document.getElementById('symbol').value,
                    timeframe: document.getElementById('timeframe').value
                })
            });
            const result = await response.json();
            showToast(result.message, result.status);
            const iconMap = {success:'✅', error:'❌', info:'ℹ️'};
            elements.analysisStatus.textContent = `${iconMap[result.status] || 'ℹ️'} ${result.message}`;
            const classMap = {success:'positive-pnl', error:'negative-pnl', info:'info-text'};
            elements.analysisStatus.className = `mt-4 text-sm ${classMap[result.status] || 'info-text'}`;
        } catch (error) {
            elements.analysisStatus.textContent = '❌ Analiz sırasında bir ağ hatası oluştu.';
            elements.analysisStatus.className = 'mt-4 text-sm negative-pnl';
        } finally {
            elements.analysisBtn.disabled = false;
        }
    }
    
    function handleConfirmOpportunity() {
        if (!currentOpportunity) return;
        socket.emit('confirm_trade', currentOpportunity);
        hideOpportunityModal();
    }

    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const toastType = ['success', 'error', 'info'].includes(type) ? type : 'info';
        toast.className = `toast toast-${toastType}`;
        toast.textContent = message;
        elements.toastContainer.appendChild(toast);
        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => elements.toastContainer.removeChild(toast), 500);
        }, 5000);
    }
    
    // --- Modal Yönetim Fonksiyonları ---
    function showOpportunityModal(opportunity) {
        elements.opportunityDetails.innerHTML = `
            <p><span class="font-semibold text-slate-300">Sembol:</span> ${opportunity.symbol}</p>
            <p><span class="font-semibold text-slate-300">Yön:</span> <span class="${opportunity.recommendation === 'AL' ? 'positive-pnl' : 'negative-pnl'}">${opportunity.recommendation}</span></p>
            <p><span class="font-semibold text-slate-300">Fiyat:</span> ${opportunity.current_price}</p>
            <p class="text-sm text-slate-400 mt-2"><span class="font-semibold text-slate-300">Gerekçe:</span> ${opportunity.reason}</p>
        `;
        elements.opportunityModal.classList.remove('hidden');
        setTimeout(() => {
            elements.opportunityModal.classList.add('opacity-100');
            elements.opportunityModal.querySelector('.modal-content').classList.add('scale-100');
        }, 10);
    }

    function hideOpportunityModal() {
        if (elements.opportunityModal.classList.contains('hidden')) return;
        elements.opportunityModal.classList.remove('opacity-100');
        elements.opportunityModal.querySelector('.modal-content').classList.remove('scale-100');
        setTimeout(() => {
            elements.opportunityModal.classList.add('hidden');
            currentOpportunity = null;
        }, 250);
    }

    function showReanalysisModal(data) {
        elements.reanalysisDetails.innerHTML = `
            <p><span class="font-semibold text-white">Sembol:</span> ${data.symbol}</p>
            <p><span class="font-semibold text-white">Tavsiye:</span> <span class="font-bold ${data.recommendation === 'KAPAT' ? 'negative-pnl' : 'positive-pnl'}">${data.recommendation}</span></p>
            <p class="text-sm mt-2"><span class="font-semibold text-white">Gerekçe:</span> ${data.reason}</p>
        `;

        elements.reanalysisActions.innerHTML = ''; 

        if (data.recommendation === 'KAPAT') {
            const closeBtn = document.createElement('button');
            closeBtn.className = 'btn btn-red';
            closeBtn.textContent = 'Pozisyonu Kapat';
            closeBtn.onclick = () => {
                handleClosePosition(data.symbol, true); // Onay penceresini atla
                hideReanalysisModal();
            };
            elements.reanalysisActions.appendChild(closeBtn);
        }

        const okBtn = document.createElement('button');
        okBtn.className = 'btn btn-gray';
        okBtn.textContent = 'Tamam';
        okBtn.onclick = hideReanalysisModal;
        elements.reanalysisActions.appendChild(okBtn);

        elements.reanalysisModal.classList.remove('hidden');
        setTimeout(() => {
            elements.reanalysisModal.classList.add('opacity-100');
            elements.reanalysisModal.querySelector('.modal-content').classList.add('scale-100');
        }, 10);
    }

    function hideReanalysisModal() {
        if (elements.reanalysisModal.classList.contains('hidden')) return;
        elements.reanalysisModal.classList.remove('opacity-100');
        elements.reanalysisModal.querySelector('.modal-content').classList.remove('scale-100');
        setTimeout(() => {
            elements.reanalysisModal.classList.add('hidden');
        }, 250);
    }
});
