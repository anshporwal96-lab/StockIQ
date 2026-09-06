/* ==========================================================================
   static/js/charts.js
   ==========================================================================
   All Chart.js drawing lives here, so stock.js can stay about data and this
   file can stay about pixels.

   Chart.js is loaded from a CDN in stock.html. It draws onto a <canvas>.
   Every chart is stored in `chartRegistry` so we can destroy and redraw it
   when the user changes the period or switches theme.
   ========================================================================== */

const chartRegistry = {};

/** Read the current theme colours out of the CSS variables. */
function themeColors() {
  const styles = getComputedStyle(document.documentElement);
  const read = (name) => styles.getPropertyValue(name).trim();
  return {
    text: read('--text-muted'),
    grid: read('--border'),
    brand: read('--brand'),
    up: read('--up'),
    down: read('--down'),
    warn: read('--warn'),
    surface: read('--surface')
  };
}

/** Remove an existing chart before drawing a new one on the same canvas. */
function destroyChart(id) {
  if (chartRegistry[id]) {
    chartRegistry[id].destroy();
    delete chartRegistry[id];
  }
}

/** Simple moving average, mirroring the Python version in utils/calculations.py. */
function movingAverage(values, period) {
  const output = new Array(values.length).fill(null);
  if (values.length < period) return output;
  let total = 0;
  for (let i = 0; i < values.length; i++) {
    total += values[i];
    if (i >= period) total -= values[i - period];
    if (i >= period - 1) output[i] = total / period;
  }
  return output;
}

/**
 * The main price line chart, with optional moving-average overlays.
 *
 * @param {Array}  candles       [{date, open, high, low, close, volume}, ...]
 * @param {Array}  activePeriods e.g. [50, 200] - which DMAs to draw
 */
function drawPriceChart(canvasId, candles, activePeriods) {
  destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !candles || candles.length === 0) return;

  const colors = themeColors();
  const labels = candles.map(c => c.date.slice(0, 10));
  const closes = candles.map(c => c.close);

  // Green when the period ended higher than it started, red otherwise.
  const rising = closes[closes.length - 1] >= closes[0];
  const lineColor = rising ? colors.up : colors.down;

  const datasets = [{
    label: 'Close',
    data: closes,
    borderColor: lineColor,
    backgroundColor: lineColor + '20',
    borderWidth: 2,
    pointRadius: 0,
    pointHitRadius: 12,
    fill: true,
    tension: 0.1
  }];

  const maColors = { 20: colors.warn, 50: colors.brand, 100: '#8e6fc4', 200: colors.text };
  (activePeriods || []).forEach(period => {
    if (closes.length < period) return;   // do not draw a line we cannot compute
    datasets.push({
      label: period + ' DMA',
      data: movingAverage(closes, period),
      borderColor: maColors[period] || colors.text,
      borderWidth: 1.4,
      pointRadius: 0,
      borderDash: [5, 4],
      fill: false,
      tension: 0.1
    });
  });

  chartRegistry[canvasId] = new Chart(canvas, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: true, labels: { color: colors.text, boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: (item) => item.dataset.label + ': Rs ' +
                             Number(item.parsed.y).toLocaleString('en-IN',
                               { minimumFractionDigits: 2, maximumFractionDigits: 2 })
          }
        }
      },
      scales: {
        x: {
          ticks: { color: colors.text, maxTicksLimit: 8, font: { size: 10 } },
          grid: { color: colors.grid, drawOnChartArea: false }
        },
        y: {
          ticks: {
            color: colors.text, font: { size: 10 },
            callback: (value) => Number(value).toLocaleString('en-IN')
          },
          grid: { color: colors.grid }
        }
      }
    }
  });
}

/** The volume bars under the price chart. */
function drawVolumeChart(canvasId, candles) {
  destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !candles || candles.length === 0) return;

  const colors = themeColors();
  chartRegistry[canvasId] = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: candles.map(c => c.date.slice(0, 10)),
      datasets: [{
        label: 'Volume',
        data: candles.map(c => c.volume),
        backgroundColor: colors.brand + '55',
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: {
          ticks: {
            color: colors.text, maxTicksLimit: 3, font: { size: 9 },
            callback: (value) => value >= 1e7 ? (value / 1e7).toFixed(1) + 'Cr'
                               : value >= 1e5 ? (value / 1e5).toFixed(1) + 'L'
                               : value
          },
          grid: { color: colors.grid }
        }
      }
    }
  });
}

/** Doughnut chart of the latest promoter / FII / DII / public split. */
function drawShareholdingChart(canvasId, quarters) {
  destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas || !quarters || quarters.length === 0) return;

  const colors = themeColors();
  const latest = quarters[quarters.length - 1];

  chartRegistry[canvasId] = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: ['Promoter', 'FII', 'DII', 'Public'],
      datasets: [{
        data: [latest.promoter, latest.fii, latest.dii, latest.public],
        backgroundColor: [colors.brand, colors.up, colors.warn, colors.text],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: colors.text, boxWidth: 12,
                                                font: { size: 11 } } },
        tooltip: { callbacks: { label: (item) => item.label + ': ' + item.parsed + '%' } }
      }
    }
  });
}

/** A grouped bar chart, used for revenue/profit and cash-flow history. */
function drawBarChart(canvasId, labels, series) {
  destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const colors = themeColors();
  const palette = [colors.brand, colors.up, colors.warn, colors.down];

  chartRegistry[canvasId] = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: series.map((s, index) => ({
        label: s.label,
        data: s.data,
        backgroundColor: (s.color || palette[index % palette.length]) + 'cc',
        borderWidth: 0
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: colors.text, boxWidth: 12, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: colors.text, font: { size: 10 } }, grid: { display: false } },
        y: {
          ticks: {
            color: colors.text, font: { size: 10 },
            callback: (value) => Number(value).toLocaleString('en-IN')
          },
          grid: { color: colors.grid }
        }
      }
    }
  });
}

/** A multi-line chart, used for margin trends and the shareholding history. */
function drawLineChart(canvasId, labels, series) {
  destroyChart(canvasId);
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const colors = themeColors();
  const palette = [colors.brand, colors.up, colors.warn, colors.down];

  chartRegistry[canvasId] = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: series.map((s, index) => ({
        label: s.label,
        data: s.data,
        borderColor: s.color || palette[index % palette.length],
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 3,
        tension: 0.25
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: colors.text, boxWidth: 12, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: colors.text, font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: colors.text, font: { size: 10 } }, grid: { color: colors.grid } }
      }
    }
  });
}

/* When the user flips between light and dark, every chart is redrawn so its
   grid lines and label colours match the new theme. */
document.addEventListener('themechange', () => {
  if (typeof window.redrawAllCharts === 'function') window.redrawAllCharts();
});
