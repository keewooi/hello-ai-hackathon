$(document).ready(function() {
    $('#generate-image-btn').on('click', function() {
        const description = $('#product-description').val();
        if (description) {
            // Add a loading indicator
            $('#generate-image-btn').prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...');

            $.ajax({
                url: '/generate-image',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ description: description }),
                success: function(response) {
                    // Assuming the response contains the image URL
                    const imageUrl = response.image_url;
                    // Create a new product card with the generated image
                    const newProductHtml = `
                        <div class="col-md-4 mb-4">
                            <div class="card product-card">
                                <img src="${imageUrl}" class="card-img-top" alt="Generated Product">
                                <div class="card-body">
                                    <h5 class="card-title">Generated Product</h5>
                                    <p class="card-text">${description}</p>
                                </div>
                            </div>
                        </div>
                    `;
                    // Add the new product to the product list
                    $('.row.justify-content-center').before(newProductHtml);
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
