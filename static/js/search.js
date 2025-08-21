document.addEventListener('DOMContentLoaded', () => {
    const productGrid = document.getElementById('product-grid');
    const searchInput = document.getElementById('search-input');
    const pageSizeSelect = document.getElementById('page-size-select');
    const paginationControls = document.getElementById('pagination-controls');
    const loadingSpinner = document.getElementById('loading-spinner');

    let pageTokens = ['']; // Store page tokens, first page is empty
    let currentPage = 0; // 0-indexed
    let isLoading = false;
    let currentQuery = 'Basic Tee'; // Default search query

    const createProductCard = (product) => {
        const card = document.createElement('div');
        card.className = 'flex flex-col gap-3 pb-3';
        
        // The product ID can be a string or number, so we handle both
        const productUrl = `/product/${product.id}`;

        card.innerHTML = `
            <a href="${productUrl}">
                <div
                  class="w-full bg-center bg-no-repeat aspect-[3/4] bg-cover rounded-lg"
                  style='background-image: url("${product.image_urls.large || product.image_urls.small}");'
                ></div>
            </a>
            <div>
              <p class="text-[#141414] text-base font-medium leading-normal">${product.name}</p>
              <p class="text-neutral-500 text-sm font-normal leading-normal">$${product.price}</p>
            </div>
        `;
        return card;
    };

    const fetchProducts = async (query = '', pageToken = '') => {
        if (isLoading) return;
        isLoading = true;
        loadingSpinner.classList.remove('hidden');
        productGrid.innerHTML = ''; // Clear grid for new page or spinner
        const pageSize = pageSizeSelect.value;

        const url = `/api/products?q=${encodeURIComponent(query)}&page_token=${pageToken}&page_size=${pageSize}`;
        
        try {
            const response = await fetch(url);
            const data = await response.json();

            if (data.products) {
                data.products.forEach(product => {
                    const card = createProductCard(product);
                    productGrid.appendChild(card);
                });

                // Store the next page token if it exists
                if (data.next_page_token && !pageTokens.includes(data.next_page_token)) {
                    pageTokens.push(data.next_page_token);
                }
            }
            updatePaginationControls(data.next_page_token);
        } catch (error) {
            console.error('Error fetching products:', error);
        } finally {
            isLoading = false;
            loadingSpinner.classList.add('hidden');
        }
    };

    const debounce = (func, delay) => {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                func.apply(this, args);
            }, delay);
        };
    };

    const updatePaginationControls = (nextPageToken) => {
        paginationControls.innerHTML = '';

        const prevButton = document.createElement('button');
        prevButton.textContent = 'Previous';
        prevButton.className = 'px-4 py-2 bg-gray-200 rounded-lg disabled:opacity-50';
        prevButton.disabled = currentPage === 0;
        prevButton.addEventListener('click', () => {
            if (currentPage > 0) {
                currentPage--;
                fetchProducts(currentQuery, pageTokens[currentPage]);
            }
        });
        paginationControls.appendChild(prevButton);

        const nextButton = document.createElement('button');
        nextButton.textContent = 'Next';
        nextButton.className = 'px-4 py-2 bg-gray-200 rounded-lg disabled:opacity-50';
        nextButton.disabled = !nextPageToken;
        nextButton.addEventListener('click', () => {
            currentPage++;
            fetchProducts(currentQuery, nextPageToken);
        });
        paginationControls.appendChild(nextButton);
    };

    const resetAndFetch = (query) => {
        currentQuery = query;
        pageTokens = [''];
        currentPage = 0;
        fetchProducts(query, pageTokens[currentPage]);
    };

    const handleSearch = debounce((query) => {
        resetAndFetch(query);
    }, 300);

    if (searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            handleSearch(e.target.value);
        });
    }

    if (pageSizeSelect) {
        pageSizeSelect.addEventListener('change', () => {
            resetAndFetch(currentQuery);
        });
    }

    // Initial load
    if (productGrid) {
        if (searchInput) {
            searchInput.value = currentQuery;
        }
        fetchProducts(currentQuery);
    }
});