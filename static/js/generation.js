$(document).ready(function() {
    $('#generate-image-btn').on('click', function() {
        const description = $('#product-description').val();
        if (description) {
            // Add a loading indicator
            $('#generate-image-btn').prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...');

            $.ajax({
                url: '/api/imagen-inspire',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ prompt: description }),
                success: function(response) {
                    const imageUrl = response.image_url;
                    const rewrittenPrompt = response.rewritten_prompt;
                    window.location.href = `/generated_product?image_url=${encodeURIComponent(imageUrl)}&description=${encodeURIComponent(rewrittenPrompt)}`;
                },
                error: function() {
                    alert('Error generating image. Please try again.');
                },
                complete: function() {
                    // Restore the button
                    $('#generate-image-btn').prop('disabled', false).html('Generate Image');
                }
            });
        } else {
            alert('Please enter a product description.');
        }
    });
});
