document.addEventListener('DOMContentLoaded', function() {
    const generateBtn = document.getElementById('generate-image-btn');
    if (generateBtn) {
        generateBtn.addEventListener('click', function() {
            const description = document.getElementById('product-description').value;
            if (description) {
                const spinner = generateBtn.querySelector('svg');
                const buttonText = generateBtn.querySelector('span');

                spinner.classList.remove('hidden');
                buttonText.textContent = 'Generating...';
                generateBtn.disabled = true;

                fetch('/api/imagen-inspire', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ prompt: description })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.image_url) {
                        window.location.href = `/generated_product?image_url=${data.image_url}&description=${data.rewritten_prompt}&title=${data.title}`;
                    } else {
                        alert('Error generating image: ' + data.error);
                        spinner.classList.add('hidden');
                        buttonText.textContent = 'Generate Inspiration!';
                        generateBtn.disabled = false;
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred while generating the image.');
                    spinner.classList.add('hidden');
                    buttonText.textContent = 'Generate Inspiration!';
                    generateBtn.disabled = false;
                });
            }
        });
    }
});
