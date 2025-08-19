# Gemini E-commerce Fashion Site

This project is a simple e-commerce fashion website that allows users to browse a catalog of clothing and accessories.

## Features

### Product Catalog

Users can browse and view a list of available fashion items.

### Virtual Try-On (VTO)

A key feature of this site is the Virtual Try-On (VTO) functionality. This allows users to see how an item might look on them before purchasing.

The VTO feature works as follows:
1.  The user uploads a personal portrait photo.
2.  The user selects a clothing or accessory item from the product listing.
3.  The application sends the user's photo and the selected item's image to a Google VTO API endpoint.
4.  The API requires both the portrait and item images to be Base64-encoded.
5.  The service returns an image with the selected item virtually "tried on" by the user.
