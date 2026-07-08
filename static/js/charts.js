/* Subreddit Charting Helper using Chart.js */

let subredditChartInstance = null;

function updateSubredditChart(profile, tab) {
    const canvas = document.getElementById('subreddit-chart');
    if (!canvas) return;

    let rawData = [];
    let label = 'Subreddit Activity';
    
    // Warm Editorial color palette (Solid colors, no gradient fills)
    let barColor = 'rgba(217, 119, 6, 0.7)'; // Solid Amber 600
    let hoverColor = '#d97706';

    if (tab === 'posts') {
        rawData = profile.subreddits_posts || [];
        label = 'Submissions';
        barColor = 'rgba(194, 65, 12, 0.7)'; // Terracotta Rust/Orange
        hoverColor = '#c2410c';
    } else if (tab === 'comments') {
        rawData = profile.subreddits_comments || [];
        label = 'Comments';
        barColor = 'rgba(71, 85, 105, 0.75)'; // Desaturated Slate Blue
        hoverColor = '#475569';
    } else {
        rawData = profile.subreddits_combined || [];
        label = 'Combined Items';
    }

    // Top 10 subreddits
    const topData = rawData.slice(0, 10);
    const labels = topData.map(item => 'r/' + item[0]);
    const counts = topData.map(item => item[1]);

    if (subredditChartInstance) {
        subredditChartInstance.destroy();
        subredditChartInstance = null;
    }

    const ctx = canvas.getContext('2d');

    subredditChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: counts,
                backgroundColor: barColor,
                hoverBackgroundColor: hoverColor,
                borderColor: 'rgba(255, 255, 255, 0.05)',
                borderWidth: 1,
                borderRadius: 4,
                barThickness: 15,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#15171c',
                    titleColor: '#f8fafc',
                    bodyColor: '#cbd5e1',
                    borderColor: '#232731',
                    borderWidth: 1,
                    padding: 8,
                    cornerRadius: 6,
                    titleFont: {
                        family: 'Space Grotesk',
                        weight: 'bold'
                    },
                    bodyFont: {
                        family: 'Plus Jakarta Sans'
                    },
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.raw} items`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(35, 39, 49, 0.5)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#64748b',
                        font: {
                            family: 'Plus Jakarta Sans',
                            size: 10
                        }
                    }
                },
                y: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#cbd5e1',
                        font: {
                            family: 'Space Grotesk',
                            weight: '500',
                            size: 11
                        }
                    }
                }
            }
        }
    });
}
