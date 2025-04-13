let lastMouseX = 0, lastMouseY = 0;

document.addEventListener('mousemove', function (e) {
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;
    if (!document.body.classList.contains('mouse-detected')) {
        document.body.classList.add('mouse-detected');
    }
    document.body.style.setProperty('--x', (lastMouseX + window.scrollX) + 'px');
    document.body.style.setProperty('--y', (lastMouseY + window.scrollY) + 'px');
});

document.addEventListener('scroll', function () {
    document.body.style.setProperty('--x', (lastMouseX + window.scrollX) + 'px');
    document.body.style.setProperty('--y', (lastMouseY + window.scrollY) + 'px');
});