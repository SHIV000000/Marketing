

document.addEventListener('DOMContentLoaded', function() {
    // Add chart.js or any other visualization library here
    // For example, you could use Chart.js to create charts for your data

    // Example: Create a pie chart for LexOffice gross vs net
    const ctx = document.getElementById('lexOfficeChart').getContext('2d');
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Gross', 'Net'],
            datasets: [{
                data: [
                    parseFloat(document.getElementById('lexOfficeGross').textContent),
                    parseFloat(document.getElementById('lexOfficeNet').textContent)
                ],
                backgroundColor: ['#36a2eb', '#ff6384']
            }]
        },
        options: {
            responsive: true,
            title: {
                display: true,
                text: 'LexOffice Gross vs Net'
            }
        }
    });
});
