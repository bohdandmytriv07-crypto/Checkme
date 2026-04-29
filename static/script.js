
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', function (e) {
        e.preventDefault();

        document.querySelectorAll('.nav-link').forEach(item => item.classList.remove('active'));
        this.classList.add('active');


        document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
        const pageId = this.getAttribute('data-page');
        document.getElementById(pageId).classList.add('active');
    });
});


document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', function () {
        document.querySelectorAll('.tab').forEach(item => item.classList.remove('active'));
        this.classList.add('active');

        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        const tabId = this.getAttribute('data-tab');
        document.getElementById(`${tabId}-tab`).classList.add('active');

        document.getElementById('result-display').style.display = 'none';
    });
});


const checkBtn = document.getElementById('btn-check-url');
const urlInput = document.getElementById('url-input');
const clearBtn = document.getElementById('btn-clear-url');
const resultDisplay = document.getElementById('result-display');
const resultTitle = document.getElementById('result-title');
const resultMessage = document.getElementById('result-message');


function looksLikeURL(str) {

    return str.includes('.') && !str.includes(' ');
}


checkBtn.addEventListener('click', async function () {
    const urlValue = urlInput.value.trim();


    if (!urlValue) {
        alert('Поле порожнє. Будь ласка, вставте посилання для перевірки.');
        return;
    }
    if (!looksLikeURL(urlValue)) {
        alert('Це не схоже на адресу сайту. Перевірте, чи немає там зайвих пробілів.');
        return;
    }


    checkBtn.disabled = true;
    checkBtn.innerText = '⌛ Перевіряємо... зачекайте';
    resultDisplay.style.display = 'none';

    try {

        const response = await fetch('/check-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: urlValue })
        });

        if (!response.ok) throw new Error('Сервер не відповідає');

        const data = await response.json();


        resultDisplay.className = `result ${data.status}`;
        resultTitle.innerText = data.title;
        resultMessage.innerText = data.message;
        resultDisplay.style.display = 'block';


        resultDisplay.scrollIntoView({ behavior: 'smooth', block: 'center' });

    } catch (error) {
        console.error('Error:', error);
        alert('Помилка зв’язку. Перевірте підключення до інтернету або статус сервера.');
    } finally {
        checkBtn.disabled = false;
        checkBtn.innerText = 'Перевірити посилання';
    }
});


urlInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        checkBtn.click();
    }
});


urlInput.addEventListener('input', function () {

    clearBtn.style.display = this.value.length > 0 ? 'flex' : 'none';
});

clearBtn.addEventListener('click', function () {
    urlInput.value = '';
    this.style.display = 'none';
    resultDisplay.style.display = 'none';
    urlInput.focus(); 
});