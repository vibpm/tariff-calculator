document.addEventListener('DOMContentLoaded', function() {
    
    // --- ИНИЦИАЛИЗАЦИЯ DOM-ЭЛЕМЕНТОВ ---
    const serviceSelectElement = document.getElementById('service');
    const choices = new Choices(serviceSelectElement, { searchResultLimit: 10, itemSelectText: 'Нажмите для выбора', placeholder: true });
    const calculateBtn = document.getElementById('calculate-btn');
    const resultContainer = document.getElementById('result-container');
    const levelsBody = document.getElementById('levels-body');
    const fixationMonthsInput = document.getElementById('fixation_months');
    const fixationCoefficientInput = document.getElementById('fixation_coefficient');
    const prepaymentMonthsInput = document.getElementById('prepayment_months');
    const levelsWarning = document.getElementById('levels-warning');
    const periodSelect = document.getElementById('period');
    const periodWarning = document.getElementById('period-warning');
    const detailsContainer = document.getElementById('calculation-details-container');
    const stepsContainer = document.getElementById('calculation-steps');
    const resultActionsContainer = document.getElementById('result-actions-container');
    const downloadBtn = document.getElementById('download-btn');
    
    let lastCalculationData = null; 
    let levelInputs = [];

    // --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (без изменений) ---
    const JS_MONTH_MAP = { 'янв': 0, 'фев': 1, 'мар': 2, 'апр': 3, 'май': 4, 'июн': 5, 'июл': 6, 'авг': 7, 'сен': 8, 'окт': 9, 'ноя': 10, 'дек': 11 };
    function parsePeriodStringJS(periodStr) { try { const [monthAbbr, yearPart] = periodStr.toLowerCase().split('.'); const monthNum = JS_MONTH_MAP[monthAbbr]; const year = 2000 + parseInt(yearPart); return new Date(year, monthNum, 1); } catch (e) { return null; } }
    function setDefaultPeriod() { const today = new Date(); const nextMonthDate = new Date(today.getFullYear(), today.getMonth() + 1, 1); const monthAbbrs = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']; const nextMonthAbbr = monthAbbrs[nextMonthDate.getMonth()]; const nextMonthYear = String(nextMonthDate.getFullYear()).slice(-2); const nextMonthString = `${nextMonthAbbr}.${nextMonthYear}`; const optionExists = Array.from(periodSelect.options).some(opt => opt.value === nextMonthString); if (optionExists) { periodSelect.value = nextMonthString; } else { if (periodSelect.options.length > 0) { periodSelect.value = periodSelect.options[periodSelect.options.length - 1].value; } } }
    function validatePeriod() { const selectedPeriodStr = periodSelect.value; const selectedDate = parsePeriodStringJS(selectedPeriodStr); if (!selectedDate) return; const today = new Date(); const startOfCurrentMonth = new Date(today.getFullYear(), today.getMonth(), 1); const periodContainer = periodSelect.closest('.form-group').querySelector('.choices__inner'); if (selectedDate < startOfCurrentMonth) { periodWarning.textContent = 'Внимание: выбран прейскурант за прошедший месяц.'; if (periodContainer) periodContainer.classList.add('is-invalid'); } else { periodWarning.textContent = ''; if (periodContainer) periodContainer.classList.remove('is-invalid'); } }
    function validateUserCount() { const service = choices.getValue(true); const isSingleUser = service && service.includes('1 пользователь'); const totalAccountsText = document.getElementById('total-accounts').textContent || '0'; const totalAccounts = parseInt(totalAccountsText.replace(/\s/g, '')) || 0; const levelsContainer = levelsBody.closest('.levels-container'); let isValid = true; levelsWarning.textContent = ''; if (levelsContainer) levelsContainer.classList.remove('is-invalid'); calculateBtn.disabled = false; if (isSingleUser && totalAccounts > 1) { levelsWarning.textContent = 'Этот тарифный план является однопользовательским.'; if (levelsContainer) levelsContainer.classList.add('is-invalid'); calculateBtn.disabled = true; isValid = false; } else if (!isSingleUser && totalAccounts === 1 && service) { levelsWarning.textContent = 'Внимание: для многопользовательского тарифа выбран только 1 пользователь.'; } return isValid; }
    function updateLiveTotals() { let totalAccounts = 0, totalMinutes = 0; levelInputs.forEach(input => { const accounts = parseInt(input.value) || 0; const level = input.dataset.level; totalAccounts += accounts; const baseMinutes = MINUTE_MAP[level] || 0; const levelTotalMinutes = accounts * baseMinutes; const minutesSpan = input.parentElement.querySelector(`.level-minutes`); if (minutesSpan) minutesSpan.textContent = levelTotalMinutes.toLocaleString('ru-RU'); totalMinutes += levelTotalMinutes; }); document.getElementById('total-accounts').textContent = totalAccounts.toLocaleString('ru-RU'); document.getElementById('total-minutes').textContent = totalMinutes.toLocaleString('ru-RU'); validateUserCount(); }
    async function updateLevels() { const selectedService = choices.getValue(true); resultContainer.innerHTML = ''; resultActionsContainer.hidden = true; lastCalculationData = null; document.getElementById('total-accounts').textContent = '0'; document.getElementById('total-minutes').textContent = '0'; if (!selectedService) { levelsBody.innerHTML = '<div class="level-placeholder">Сначала выберите тарифный план</div>'; return; } levelsBody.innerHTML = '<div class="level-placeholder">Загрузка уровней...</div>'; try { const response = await fetch(`/get_levels_for_service/${encodeURIComponent(selectedService)}`); const availableLevels = await response.json(); levelsBody.innerHTML = ''; if (availableLevels.length === 0) { levelsBody.innerHTML = '<div class="level-placeholder">Для этого плана уровни не найдены</div>'; return; } availableLevels.forEach(level => { const row = document.createElement('div'); row.className = 'level-row'; row.innerHTML = ` <label>${level}</label> <input type="number" class="level-input" data-level="${level}" min="0" placeholder="0"> <span class="level-minutes" data-level-minutes="${level}">0</span> `; levelsBody.appendChild(row); }); levelInputs = document.querySelectorAll('.level-input'); levelInputs.forEach(input => input.addEventListener('input', updateLiveTotals)); updateLiveTotals(); } catch (error) { levelsBody.innerHTML = '<div class="level-placeholder error">Ошибка загрузки уровней</div>'; console.error("Ошибка при получении уровней:", error); } }
    
    // --- НАЗНАЧЕНИЕ ОБРАБОТЧИКОВ СОБЫТИЙ ---
    serviceSelectElement.addEventListener('change', updateLevels);
    periodSelect.addEventListener('change', validatePeriod);
    fixationMonthsInput.addEventListener('input', () => { const months = parseInt(fixationMonthsInput.value) || 0; const coefficient = FIXATION_COEFFICIENT_MAP[months] || 1.0; fixationCoefficientInput.value = coefficient.toFixed(2); });
    setDefaultPeriod();
    validatePeriod();

    // --- ОБРАБОТЧИК КНОПКИ "РАССЧИТАТЬ" ---
    calculateBtn.addEventListener('click', async () => {
        const requestPayload = { period: periodSelect.value, service: choices.getValue(true), prepayment_months: parseInt(prepaymentMonthsInput.value, 10), discount_percent: parseFloat(document.getElementById('discount_percent').value) || 0, fixation_months: parseInt(fixationMonthsInput.value) || 0, levels: Array.from(levelInputs).map(input => ({ level: input.dataset.level, accounts: parseInt(input.value) || 0 })).filter(item => item.accounts > 0) };
        calculateBtn.disabled = true; calculateBtn.textContent = 'Расчет...'; resultContainer.innerHTML = ''; prepaymentMonthsInput.classList.remove('is-invalid'); detailsContainer.hidden = true; stepsContainer.innerHTML = '';
        resultActionsContainer.hidden = true;
        lastCalculationData = null;

        if (!validateUserCount() || !requestPayload.service || requestPayload.levels.length === 0) { resultContainer.innerHTML = `<p class="error">Пожалуйста, выберите тарифный план и укажите количество пользователей.</p>`; calculateBtn.disabled = false; calculateBtn.textContent = 'Рассчитать'; return; }
        const isLDService = requestPayload.service.includes('ЛД');
        if (isLDService && requestPayload.prepayment_months < 4) { resultContainer.innerHTML = `<p class="error">Внимание! Для ТП 'ЛД' предоплата не может быть меньше 4 месяцев.</p>`; prepaymentMonthsInput.classList.add('is-invalid'); calculateBtn.disabled = false; calculateBtn.textContent = 'Рассчитать'; return; }

        try {
            const response = await fetch('/calculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestPayload) });
            const data = await response.json();
            if (response.ok && !data.error) {
                const summary = data.price_summary; const totals = data.totals; const prepayment_months = requestPayload.prepayment_months; const discount_percent = requestPayload.discount_percent; const fixation_months = requestPayload.fixation_months;
                let warningHtml = data.warning ? `<p class="error">${data.warning}</p>` : '';
                resultContainer.innerHTML = ` ${warningHtml} <h4>Итоговый расчет для ${totals.accounts} пользователей:</h4> <div class="price-summary-table"> <div class="price-summary-header">Цена</div> <div class="price-summary-header">За период (${prepayment_months} мес.)</div> <div class="price-summary-header">Ежемесячно</div> <div class="price-summary-row">По прейскуранту</div> <div class="price-summary-row">${summary.list_period.toFixed(2).replace('.', ',')} руб.</div> <div class="price-summary-row">${summary.list_monthly.toFixed(2).replace('.', ',')} руб.</div> ${discount_percent > 0 ? ` <div class="price-summary-row">Итого со скидкой</div> <div class="price-summary-row">${summary.discounted_period.toFixed(2).replace('.', ',')} руб.</div> <div class="price-summary-row">${summary.discounted_monthly.toFixed(2).replace('.', ',')} руб.</div> ` : ''} ${fixation_months > 0 ? ` <div class="price-summary-row total-row">Итого с фиксацией</div> <div class="price-summary-row total-row"><strong>${summary.fixed_period.toFixed(2).replace('.', ',')} руб.</strong></div> <div class="price-summary-row total-row"><strong>${summary.fixed_monthly.toFixed(2).replace('.', ',')} руб.</strong></div> ` : ''} </div> `;
                lastCalculationData = requestPayload;
                resultActionsContainer.hidden = false;
                
                // ===== ИЗМЕНЕНИЕ ЗДЕСЬ: Плавный скролл к результатам =====
                resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });

            } else { resultContainer.innerHTML = `<p class="error">${data.error || data.detail}</p>`; }
        } catch(e) { resultContainer.innerHTML = `<p class="error">Ошибка сети или обработки ответа.</p>`; }
        finally { calculateBtn.disabled = false; calculateBtn.textContent = 'Рассчитать'; }
    });

    // --- ОБРАБОТЧИК КНОПКИ "СКАЧАТЬ КП" (без изменений) ---
    downloadBtn.addEventListener('click', async () => {
        if (!lastCalculationData) { alert("Сначала выполните расчет."); return; }
        downloadBtn.disabled = true; downloadBtn.textContent = 'Генерация документа...';
        try {
            const response = await fetch('/download_offer', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(lastCalculationData) });
            if (!response.ok) { const errorData = await response.json(); alert(`Ошибка создания документа: ${errorData.detail || 'Неизвестная ошибка'}`); return; }
            const contentDisposition = response.headers.get('content-disposition');
            let filename = 'commercial_offer.docx';
            if (contentDisposition) { const matchUtf8 = contentDisposition.match(/filename\*=UTF-8''(.+)/i); if (matchUtf8) { filename = decodeURIComponent(matchUtf8[1]); } else { const matchAscii = contentDisposition.match(/filename="(.+)"/i); if (matchAscii) { filename = matchAscii[1]; } } }
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none'; a.href = url; a.download = filename;
            document.body.appendChild(a); a.click();
            window.URL.revokeObjectURL(url); document.body.removeChild(a);
        } catch (error) { console.error('Ошибка при скачивании файла:', error); alert('Произошла ошибка при скачивании файла.'); } 
        finally { downloadBtn.disabled = false; downloadBtn.textContent = 'Скачать коммерческое предложение'; }
    });
});