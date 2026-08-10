// Phone mask — автоопределение длины кода страны
export function initPhoneMasks() {
    document.querySelectorAll('input[type="tel"]').forEach(phoneInput => {
        if (phoneInput.dataset.maskInit) return;
        phoneInput.dataset.maskInit = '1';

        function formatPhone(digits) {
            if (!digits.length) return '';

            let codeLen = 1;
            if (digits.startsWith('7') || digits.startsWith('1')) codeLen = 1;
            else if (digits.startsWith('99')) codeLen = 3;
            else codeLen = 2;

            const code = digits.slice(0, codeLen);
            const rest = digits.slice(codeLen);

            let formatted = '+' + code;
            if (rest.length > 0) formatted += ' (' + rest.slice(0, 3);
            if (rest.length >= 3) formatted += ')';
            if (rest.length > 3) formatted += ' ' + rest.slice(3, 6);
            if (rest.length > 6) formatted += '-' + rest.slice(6, 8);
            if (rest.length > 8) formatted += '-' + rest.slice(8, 10);

            return formatted;
        }

        phoneInput.addEventListener('input', (e) => {
            let digits = e.target.value.replace(/\D/g, '');
            if (digits.length > 15) digits = digits.slice(0, 15);
            e.target.value = formatPhone(digits);
        });

        phoneInput.addEventListener('focus', () => {
            if (!phoneInput.value) phoneInput.value = '+';
        });

        phoneInput.addEventListener('blur', () => {
            if (phoneInput.value === '+') phoneInput.value = '';
        });

        phoneInput.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && phoneInput.value.length <= 1) {
                phoneInput.value = '';
                e.preventDefault();
            }
        });
    });
}
