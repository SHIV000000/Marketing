// dashboard.js

document.addEventListener('DOMContentLoaded', function() {
    // Revenue Sources Chart
    var revenueCtx = document.getElementById('revenueSourcesChart').getContext('2d');
    var revenueSourcesChart = new Chart(revenueCtx, {
        type: 'pie',
        data: {
            labels: ['LexOffice/Sevdesk', 'Manual Entries', 'Bank Transactions'],
            datasets: [{
                data: [
                    parseFloat(document.getElementById('lexSevPercentage').textContent),
                    parseFloat(document.getElementById('manualPercentage').textContent),
                    parseFloat(document.getElementById('bankPercentage').textContent)
                ],
                backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Revenue Sources'
                }
            }
        }
    });

    // Google Ads Chart
    var googleAdsCtx = document.getElementById('googleAdsChart').getContext('2d');
    var googleAdsChart = new Chart(googleAdsCtx, {
        type: 'bar',
        data: {
            labels: ['Total Budget', 'Number of Campaigns'],
            datasets: [{
                label: 'Google Ads',
                data: [
                    parseFloat(document.getElementById('googleAdsBudget').textContent),
                    parseInt(document.getElementById('googleAdsCampaigns').textContent)
                ],
                backgroundColor: ['#4BC0C0', '#FF9F40']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Google Ads Overview'
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Function to format currency
    function formatCurrency(amount) {
        return new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(amount);
    }
    
    // Function to update dashboard data
    function updateDashboard() {
        fetch('/analyze/' + agencyId)  // You'll need to set agencyId somewhere in your template
            .then(response => response.json())
            .then(data => {
                // Update LexOffice/Sevdesk card
                document.querySelector('#lexSevGross').textContent = formatCurrency(data.lex_sev.total_gross);
                document.querySelector('#lexSevNet').textContent = formatCurrency(data.lex_sev.total_net);
                document.querySelector('#lexSevCustomers').textContent = data.lex_sev.customer_count;
                document.querySelector('#lexSevAverage').textContent = formatCurrency(data.lex_sev.average_per_customer);
    
                // Update Bank Transactions card
                document.querySelector('#bankTransactions').textContent = data.bank.total_transactions;
                document.querySelector('#bankAmount').textContent = formatCurrency(data.bank.total_amount);
                document.querySelector('#bankAverage').textContent = formatCurrency(data.bank.average_per_transaction);
    
                // Update Google Ads card
                document.querySelector('#googleAdsBudget').textContent = formatCurrency(data.google_ads.total_budget);
                document.querySelector('#googleAdsCampaigns').textContent = data.google_ads.total_campaigns;
                document.querySelector('#googleAdsAverage').textContent = formatCurrency(data.google_ads.average_budget_per_campaign);
    
                // Update Manual Entries card
                document.querySelector('#manualAmount').textContent = formatCurrency(data.manual.total_amount);
                document.querySelector('#manualCount').textContent = data.manual.entry_count;
                document.querySelector('#manualAverage').textContent = formatCurrency(data.manual.average_per_entry);
    
                // Update Overall Comparison card
                document.querySelector('#totalRevenue').textContent = formatCurrency(data.comparison.total_revenue);
                document.querySelector('#lexSevPercentage').textContent = data.comparison.lex_sev_percentage.toFixed(2) + '%';
                document.querySelector('#manualPercentage').textContent = data.comparison.manual_percentage.toFixed(2) + '%';
                document.querySelector('#bankPercentage').textContent = data.comparison.bank_percentage.toFixed(2) + '%';
                document.querySelector('#googleAdsPercentage').textContent = data.comparison.google_ads_budget_percentage.toFixed(2) + '%';
    
                // Update charts
                updateRevenueSourcesChart(data.comparison);
                updateGoogleAdsChart(data.google_ads);
            })
            .catch(error => console.error('Error updating dashboard:', error));
    }
    
    function updateRevenueSourcesChart(data) {
        revenueSourcesChart.data.datasets[0].data = [
            data.lex_sev_percentage,
            data.manual_percentage,
            data.bank_percentage
        ];
        revenueSourcesChart.update();
    }
    
    function updateGoogleAdsChart(data) {
        googleAdsChart.data.datasets[0].data = [data.total_budget, data.total_campaigns];
        googleAdsChart.update();
    }
    
    // Call updateDashboard every 5 minutes
    setInterval(updateDashboard, 300000);

    // Add event listener for manual refresh
    document.getElementById('refreshDashboard').addEventListener('click', updateDashboard);
});
