document.addEventListener('DOMContentLoaded', function() {
    const uploadTab = document.getElementById('upload-tab');
    const modelTab = document.getElementById('model-tab');
    const uploadSection = document.getElementById('upload-section');
    const modelSection = document.getElementById('model-section');
    const modelSelections = document.querySelectorAll('.model-selection');
    const profilePicInput = document.getElementById('profile-pic');
    const proceedBtn = document.getElementById('proceed-btn');
    const imagePreview = document.getElementById('image-preview');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const removeImageBtn = document.getElementById('remove-image-btn');
    let uploadedImageUrl = null;

    uploadTab.addEventListener('click', (e) => {
        e.preventDefault();
        uploadTab.querySelector('p').classList.add('text-[#141414]');
        uploadTab.querySelector('p').classList.remove('text-neutral-500');
        uploadTab.classList.add('border-b-[#141414]');
        uploadTab.classList.remove('border-b-transparent');

        modelTab.querySelector('p').classList.add('text-neutral-500');
        modelTab.querySelector('p').classList.remove('text-[#141414]');
        modelTab.classList.add('border-b-transparent');
        modelTab.classList.remove('border-b-[#141414]');

        uploadSection.classList.remove('hidden');
        modelSection.classList.add('hidden');
    });

    modelTab.addEventListener('click', (e) => {
        e.preventDefault();
        modelTab.querySelector('p').classList.add('text-[#141414]');
        modelTab.querySelector('p').classList.remove('text-neutral-500');
        modelTab.classList.add('border-b-[#141414]');
        modelTab.classList.remove('border-b-transparent');

        uploadTab.querySelector('p').classList.add('text-neutral-500');
        uploadTab.querySelector('p').classList.remove('text-[#141414]');
        uploadTab.classList.add('border-b-transparent');
        uploadTab.classList.remove('border-b-[#141414]');

        modelSection.classList.remove('hidden');
        uploadSection.classList.add('hidden');
    });

    function checkCanProceed() {
        const selectedModel = document.querySelector('.model-selection.selected');
        const fileUploaded = profilePicInput.files.length > 0;
        proceedBtn.disabled = !selectedModel && !fileUploaded;
    }

    modelSelections.forEach(function(model) {
        model.addEventListener('click', function() {
            modelSelections.forEach(function(m) {
                if (m !== model) {
                    m.classList.remove('selected', 'border', 'border-blue-500');
                }
            });
            model.classList.toggle('selected');
            if (model.classList.contains('selected')) {
                model.classList.add('border', 'border-blue-500');
            } else {
                model.classList.remove('border', 'border-blue-500');
            }
            profilePicInput.value = ''; // Clear file input
            uploadedImageUrl = null;
            imagePreviewContainer.style.display = 'none';
            checkCanProceed();
        });
    });

    profilePicInput.addEventListener('change', function(event) {
        modelSelections.forEach(function(m) {
            m.classList.remove('selected', 'border', 'border-blue-500');
        });

        const [file] = event.target.files;
        if (file) {
            imagePreview.src = URL.createObjectURL(file);
            imagePreviewContainer.style.display = 'block';
        } else {
            imagePreviewContainer.style.display = 'none';
        }

        checkCanProceed();
    });

    removeImageBtn.addEventListener('click', function() {
        profilePicInput.value = '';
        imagePreview.src = '';
        imagePreviewContainer.style.display = 'none';
        checkCanProceed();
    });

    proceedBtn.addEventListener('click', function() {
        const selectedProducts = document.querySelectorAll('.product-image-container').length;

        if (selectedProducts === 0) {
            alert('Please select at least one product.');
            return;
        }

        const file = profilePicInput.files[0];
        const selectedModelImage = document.querySelector('.model-selection.selected');

        if (!file && !selectedModelImage) {
            alert('Please select a model or upload your photo.');
            return;
        }

        const loadingModal = document.getElementById('loadingModal');
        loadingModal.classList.remove('hidden');

        if (file) {
            const formData = new FormData();
            formData.append('file', file);

            fetch('/api/upload', {
                method: 'POST',
                body: formData,
            })
            .then(response => response.json())
            .then(data => {
                if (data.image_url) {
                    uploadedImageUrl = data.image_url;
                    proceedWithTryOn(uploadedImageUrl);
                } else {
                    loadingModal.classList.add('hidden');
                    alert('Error uploading image: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                loadingModal.classList.add('hidden');
                console.error('Error:', error);
                alert('Error uploading image.');
            });
        } else {
            proceedWithTryOn(selectedModelImage.src);
        }
    });

    function proceedWithTryOn(personImagePath) {
        const clothing_image_paths = Array.from(document.querySelectorAll('.product-image-container .bg-cover')).map(div => {
            const style = window.getComputedStyle(div);
            const backgroundImage = style.getPropertyValue('background-image');
            return backgroundImage.slice(4, -1).replace(/"/g, "");
        });


        fetch('/api/virtual-try-on', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                person_image_gcs_uri: personImagePath,
                apparel_gcs_uris: clothing_image_paths
            }),
        })
        .then(response => response.json())
        .then(data => {
            const loadingModal = document.getElementById('loadingModal');
            loadingModal.classList.add('hidden');
            if (data.image_url) {
                const resultsContainer = document.getElementById('results-container');
                const resultsImageContainer = document.getElementById('results-image-container');
                resultsImageContainer.innerHTML = `<img src="${data.image_url}" class="img-fluid" alt="Virtual Try-On Result">`;
                resultsContainer.style.display = 'block';
            } else {
                alert('Error generating image: ' + (data.error || 'Unknown error'));
            }
        })
        .catch((error) => {
            const loadingModal = document.getElementById('loadingModal');
            loadingModal.classList.add('hidden');
            console.error('Error:', error);
            alert('Error sending virtual try-on request.');
        });
    }
});