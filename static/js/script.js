// --- Полная версия static/js/script.js ---

document.addEventListener('DOMContentLoaded', function() {
    
    // --- ИНИЦИАЛИЗАЦИЯ DOM-ЭЛЕМЕНТОВ ---
    const serviceSelectElement = document.getElementById('service');
    const periodSelect = document.getElementById('period');
    const fixationBlock = document.getElementById('fixation-block');

    const serviceChoices = new Choices(serviceSelectElement, { searchResultLimit: 10, itemSelectText: 'Нажмите для выбора', placeholder: true });
    
    const serviceChoicesElement = serviceSelectElement.closest('.choices');
    if (serviceChoicesElement) {
        const searchInput = serviceChoicesElement.querySelector('input.choices__input');
        if (searchInput) {
            searchInput.setAttribute('aria-label', 'Поиск по тарифным планам');
        }
    }

    const calculateBtn = document.getElementById('calculate-btn');
    const resultContainer = document.getElementById('result-container');
    const levelsBody = document.getElementById('levels-body');
    const fixationMonthsInput = document.getElementById('fixation_months');
    const fixationCoefficientInput = document.getElementById('fixation_coefficient');
    const prepaymentContainer = document.getElementById('prepayment-container');
    let prepaymentInput = document.getElementById('prepayment_months');
    const discountPercentInput = document.getElementById('discount_percent');
    const levelsWarning = document.getElementById('levels-warning');
    const periodWarning = document.getElementById('period-warning');
    const resultActionsContainer = document.getElementById('result-actions-container');
    const downloadBtn = document.getElementById('download-btn');
    const promotionSelect = document.getElementById('promotion');
    const promotionDiscountInput = document.getElementById('promotion_discount');
    const promotionCondition2Input = document.getElementById('promotion_condition2');
    
    let allPromotionsData = {};
    let lastCalculationData = null; 
    let levelInputs = [];
    let currentMinuteMap = {};

    // --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

    function toggleFixationFieldsVisibility() {
        const selectedService = serviceChoices.getValue(true) || '';
        const isLdService = selectedService.includes('ЛД');
        fixationBlock.classList.toggle('hidden', isLdService);
        if (isLdService) {
            fixationMonthsInput.value = 0;
            fixationMonthsInput.dispatchEvent(new Event('input')); 
        }
    }

    const JS_MONTH_MAP = { 'янв': 0, 'фев': 1, 'мар': 2, 'апр': 3, 'май': 4, 'июн': 5, 'июл': 6, 'авг': 7, 'сен': 8, 'окт': 9, 'ноя': 10, 'дек': 11 };
    function parsePeriodStringJS(periodStr) { try { if(!periodStr) return null; const [monthAbbr, yearPart] = periodStr.toLowerCase().split('.'); const monthNum = JS_MONTH_MAP[monthAbbr]; const year = 2000 + parseInt(yearPart); return new Date(year, monthNum, 1); } catch (e) { return null; } }
    
    function setDefaultPeriod() {
        const today = new Date();
        const nextMonthDate = new Date(today.getFullYear(), today.getMonth() + 1, 1);
        const availablePeriods = Array.from(periodSelect.options).map(option => ({ value: option.value, date: parsePeriodStringJS(option.value) })).filter(p => p.date !== null);
        if (availablePeriods.length === 0) return;
        let bestChoice = availablePeriods.find(p => p.date >= nextMonthDate);
        if (!bestChoice) { bestChoice = availablePeriods[availablePeriods.length - 1]; }
        if (bestChoice) { periodSelect.value = bestChoice.value; }
    }

    function validatePeriod() { const selectedPeriodStr = periodSelect.value; const selectedDate = parsePeriodStringJS(selectedPeriodStr); if (!selectedDate) return; const today = new Date(); const startOfCurrentMonth = new Date(today.getFullYear(), today.getMonth(), 1); if (selectedDate < startOfCurrentMonth) { periodWarning.textContent = 'Внимание: выбран прейскурант за прошедший месяц.'; periodSelect.classList.add('is-invalid'); } else { periodWarning.textContent = ''; periodSelect.classList.remove('is-invalid'); } }
    function validateUserCount() { const service = serviceChoices.getValue(true); const isSingleUser = service && service.includes('1 пользователь'); const totalAccountsText = document.getElementById('total-accounts').textContent || '0'; const totalAccounts = parseInt(totalAccountsText.replace(/\s/g, '')) || 0; const levelsContainer = levelsBody.closest('.levels-container'); let isValid = true; levelsWarning.textContent = ''; if (levelsContainer) levelsContainer.classList.remove('is-invalid'); calculateBtn.disabled = false; if (isSingleUser && totalAccounts > 1) { levelsWarning.textContent = 'Этот тарифный план является однопользовательским.'; if (levelsContainer) levelsContainer.classList.add('is-invalid'); calculateBtn.disabled = true; isValid = false; } else if (!isSingleUser && totalAccounts === 1 && service) { levelsWarning.textContent = 'Внимание: для многопользовательского тарифа выбран только 1 пользователь.'; } return isValid; }

    function updatePromoDetailsFromPrepayment() {
        const promoId = promotionSelect.value;
        const promoData = allPromotionsData[promoId];
        if (!promoData) return;

        const selectedMonths = parseInt(prepaymentInput.value);
        const variant = promoData.variants.find(v => v.months === selectedMonths);

        if (variant) {
            promotionDiscountInput.value = `${variant.discount_percent.toFixed(2)}%`;
            promotionCondition2Input.value = variant.condition2 || "-";
        }
    }

    function showPrepaymentSelect(promoData) {
        const select = document.createElement('select');
        select.id = 'prepayment_months';
        promoData.variants.forEach(variant => {
            const option = document.createElement('option');
            option.value = variant.months;
            option.textContent = variant.months;
            select.appendChild(option);
        });
        
        prepaymentContainer.innerHTML = '';
        prepaymentContainer.appendChild(select);
        prepaymentInput = select;
        prepaymentInput.addEventListener('change', updatePromoDetailsFromPrepayment);
    }

    function showPrepaymentInput() {
        const input = document.createElement('input');
        input.type = 'number';
        input.id = 'prepayment_months';
        input.value = '1';
        input.min = '1';

        prepaymentContainer.innerHTML = '';
        prepaymentContainer.appendChild(input);
        prepaymentInput = input;
    }

    function handlePromotionChange() {
        const selectedPromoId = promotionSelect.value;
        const promoData = allPromotionsData[selectedPromoId];

        if (promoData) {
            showPrepaymentSelect(promoData);
            updatePromoDetailsFromPrepayment();
            discountPercentInput.value = 0;
            discountPercentInput.disabled = true;
        } else {
            showPrepaymentInput();
            promotionDiscountInput.value = "-";
            promotionCondition2Input.value = "-";
            discountPercentInput.disabled = false;
        }
    }
    
    async function updateAvailablePromotions() {
        const service = serviceChoices.getValue(true);
        const selectedLevels = Array.from(levelInputs)
            .filter(input => (parseInt(input.value) || 0) > 0)
            .map(input => input.dataset.level);

        if (!service || selectedLevels.length === 0) {
            promotionSelect.innerHTML = '<option value="no_promotion">Нет акции</option>';
            promotionSelect.disabled = true;
            allPromotionsData = {};
            handlePromotionChange();
            return;
        }

        try {
            const response = await fetch('/get_all_promotions_for_selection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service: service, levels: selectedLevels })
            });
            const promotions = await response.json();
            allPromotionsData = promotions;

            promotionSelect.innerHTML = '<option value="no_promotion">Нет акции</option>';
            const promoKeys = Object.keys(promotions);
            
            if (promoKeys.length > 0) {
                promoKeys.forEach(key => {
                    const promo = promotions[key];
                    const option = document.createElement('option');
                    option.value = promo.id;
                    option.textContent = promo.name;
                    promotionSelect.appendChild(option);
                });
                promotionSelect.disabled = false;
            } else {
                promotionSelect.disabled = true;
            }
            handlePromotionChange();
        } catch (error) {
            console.error("Ошибка при загрузке всех акций:", error);
            promotionSelect.innerHTML = '<option value="no_promotion">Нет акции</option>';
            promotionSelect.disabled = true;
            allPromotionsData = {};
            handlePromotionChange();
        }
    }

    function updateLiveTotals() {
        let totalAccounts = 0;
        let activeLevelsInfo = [];
        levelInputs.forEach(input => {
            const accounts = parseInt(input.value) || 0;
            const levelName = input.dataset.level;
            const minutesSpan = input.parentElement.querySelector(`.level-minutes`);
            if (accounts > 0) {
                const baseMinutes = currentMinuteMap[levelName] || '0';
                activeLevelsInfo.push({ accounts, baseMinutes });
                totalAccounts += accounts;
                if (minutesSpan) {
                    const isNumeric = String(baseMinutes).match(/^\d+$/);
                    minutesSpan.textContent = isNumeric ? (accounts * parseInt(baseMinutes)).toLocaleString('ru-RU') : baseMinutes;
                }
            } else {
                if (minutesSpan) minutesSpan.textContent = '0';
            }
        });
        let totalMinutesDisplay = '0';
        if (activeLevelsInfo.length === 1 && !String(activeLevelsInfo[0].baseMinutes).match(/^\d+$/)) {
            totalMinutesDisplay = activeLevelsInfo[0].baseMinutes;
        } else {
            const numericTotal = activeLevelsInfo.reduce((sum, level) => {
                const minutes = parseInt(level.baseMinutes);
                return sum + (isNaN(minutes) ? 0 : level.accounts * minutes);
            }, 0);
            totalMinutesDisplay = numericTotal.toLocaleString('ru-RU');
        }
        document.getElementById('total-accounts').textContent = totalAccounts.toLocaleString('ru-RU');
        document.getElementById('total-minutes').textContent = totalMinutesDisplay;
        validateUserCount();
        updateAvailablePromotions();
    }

    async function updateLevels() {
        toggleFixationFieldsVisibility();
        const selectedService = serviceChoices.getValue(true);
        resultContainer.innerHTML = '';
        resultActionsContainer.hidden = true;
        lastCalculationData = null;
        document.getElementById('total-accounts').textContent = '0';
        document.getElementById('total-minutes').textContent = '0';
        updateAvailablePromotions();
        if (!selectedService) {
            levelsBody.innerHTML = '<div class="level-placeholder">Сначала выберите тарифный план</div>';
            return;
        }
        levelsBody.innerHTML = '<div class="level-placeholder">Загрузка уровней...</div>';
        try {
            const response = await fetch(`/get_levels_for_service/${encodeURIComponent(selectedService)}`);
            const availableLevelsData = await response.json();
            levelsBody.innerHTML = '';
            
            if (availableLevelsData.length === 0) {
                levelsBody.innerHTML = '<div class="level-placeholder">Для этого плана уровни не найдены</div>';
                return;
            }

            currentMinuteMap = {};
            
            availableLevelsData.forEach(levelData => {
                const levelName = levelData.Уровень;
                const minutes = levelData.Минут;
                currentMinuteMap[levelName] = minutes;
                const inputId = `level-input-${levelName.replace(/[\s/(),]+/g, '-').toLowerCase()}`;
                const row = document.createElement('div');
                row.className = 'level-row';
                row.innerHTML = `
                    <label for="${inputId}">${levelName}</label>
                    <input type="number" class="level-input" id="${inputId}" data-level="${levelName}" min="0" placeholder="0">
                    <span class="level-minutes" data-level-minutes="${levelName}">0</span>
                `;
                levelsBody.appendChild(row);
            });

            levelInputs = document.querySelectorAll('.level-input');
            levelInputs.forEach(input => input.addEventListener('input', updateLiveTotals));
            updateLiveTotals();
        } catch (error) {
            levelsBody.innerHTML = '<div class="level-placeholder error">Ошибка загрузки уровней</div>';
            console.error("Ошибка при получении уровней:", error);
        }
    }
    
    // --- ОБРАБОТЧИКИ СОБЫТИЙ ---
    serviceSelectElement.addEventListener('change', updateLevels);
    promotionSelect.addEventListener('change', handlePromotionChange);
    periodSelect.addEventListener('change', validatePeriod);
    fixationMonthsInput.addEventListener('input', () => { const months = parseInt(fixationMonthsInput.value) || 0; const coefficient = FIXATION_COEFFICIENT_MAP[months] || 1.0; fixationCoefficientInput.value = coefficient.toFixed(2); });
    
    calculateBtn.addEventListener('click', async () => {
        const requestPayload = { period: periodSelect.value, service: serviceChoices.getValue(true), prepayment_months: parseInt(prepaymentInput.value, 10), discount_percent: parseFloat(document.getElementById('discount_percent').value) || 0, fixation_months: parseInt(fixationMonthsInput.value) || 0, levels: Array.from(levelInputs).map(input => ({ level: input.dataset.level, accounts: parseInt(input.value) || 0 })).filter(item => item.accounts > 0), promotion_id: promotionSelect.value };
        calculateBtn.disabled = true; calculateBtn.textContent = 'Расчет...'; resultContainer.innerHTML = ''; prepaymentInput.classList.remove('is-invalid');
        resultActionsContainer.hidden = true;
        lastCalculationData = null;
        if (!validateUserCount() || !requestPayload.service || requestPayload.levels.length === 0) { resultContainer.innerHTML = `<p class="error">Пожалуйста, выберите тарифный план и укажите количество пользователей.</p>`; calculateBtn.disabled = false; calculateBtn.textContent = 'Рассчитать'; return; }
        const isLDService = requestPayload.service.includes('ЛД');
        if (isLDService && requestPayload.prepayment_months < 4) { resultContainer.innerHTML = `<p class="error">Внимание! Для ТП 'ЛД' предоплата не может быть меньше 4 месяцев.</p>`; prepaymentInput.classList.add('is-invalid'); calculateBtn.disabled = false; calculateBtn.textContent = 'Рассчитать'; return; }
        try {
            const response = await fetch('/calculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestPayload) });
            const data = await response.json();
            if (response.ok && !data.error) {
                const summary = data.price_summary; const totals = data.totals; const prepayment_months = requestPayload.prepayment_months;
                const isPromoApplied = requestPayload.promotion_id && requestPayload.promotion_id !== 'no_promotion';
                const discount_percent = isPromoApplied ? (allPromotionsData[requestPayload.promotion_id]?.variants.find(v => v.months === prepayment_months)?.discount_percent || 0) : requestPayload.discount_percent;
                const fixation_months = requestPayload.fixation_months;
                let warningHtml = data.warning ? `<p class="error">${data.warning}</p>` : '';
                const showDiscountRow = discount_percent > 0 || isPromoApplied;
                resultContainer.innerHTML = ` ${warningHtml} <h4>Итоговый расчет для ${totals.accounts} пользователей:</h4> <div class="price-summary-table"> <div class="price-summary-header">Цена</div> <div class="price-summary-header">За период (${prepayment_months} мес.)</div> <div class="price-summary-header">Ежемесячно</div> <div class="price-summary-row">По прейскуранту</div> <div class="price-summary-row">${summary.list_period.toFixed(2).replace('.', ',')} руб.</div> <div class="price-summary-row">${summary.list_monthly.toFixed(2).replace('.', ',')} руб.</div> ${showDiscountRow ? ` <div class="price-summary-row">Итого со скидкой</div> <div class="price-summary-row">${summary.discounted_period.toFixed(2).replace('.', ',')} руб.</div> <div class="price-summary-row">${summary.discounted_monthly.toFixed(2).replace('.', ',')} руб.</div> ` : ''} ${fixation_months > 0 ? ` <div class="price-summary-row total-row">Итого с фиксацией</div> <div class="price-summary-row total-row"><strong>${summary.fixed_period.toFixed(2).replace('.', ',')} руб.</strong></div> <div class="price-summary-row total-row"><strong>${summary.fixed_monthly.toFixed(2).replace('.', ',')} руб.</strong></div> ` : ''} </div> `;
                lastCalculationData = requestPayload;
                resultActionsContainer.hidden = false;
                resultActionsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else { resultContainer.innerHTML = `<p class="error">${data.error || data.detail}</p>`; }
        } catch(e) { resultContainer.innerHTML = `<p class="error">Ошибка сети или обработки ответа.</p>`; }
        finally { calculateBtn.disabled = false; calculateBtn.textContent = 'Рассчитать'; }
    });

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
    
    // --- ПЕРВИЧНАЯ ЗАГРУЗКА ---
    setDefaultPeriod();
    validatePeriod();
    toggleFixationFieldsVisibility();
});