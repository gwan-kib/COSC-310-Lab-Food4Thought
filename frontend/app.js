// Customer restaurant-discovery page with navigation to the REST-backed edit form.
// Restaurant and menu data comes from the API, never directly from JSON storage.
// API text is always rendered with textContent, never parsed as HTML, because
// restaurants can be created by anyone through POST /restaurants.

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function getJson(path) {
  let response;
  try {
    response = await fetch(path, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError(0, "Could not reach the server.");
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    // A non-JSON body still produces a readable error below.
  }

  if (!response.ok) {
    const detail = body && typeof body.detail === "string" ? body.detail : null;
    throw new ApiError(response.status, detail || `Request failed (HTTP ${response.status}).`);
  }
  return body;
}

const listStatus = document.getElementById("list-status");
const restaurantList = document.getElementById("restaurant-list");
const filterForm = document.getElementById("filter-form");
const cuisineInput = document.getElementById("cuisine-input");
const clearFilter = document.getElementById("clear-filter");

const detailsStatus = document.getElementById("details-status");
const detailsContent = document.getElementById("details-content");
const detailsName = document.getElementById("details-name");
const detailsCuisine = document.getElementById("details-cuisine");
const detailsDescription = document.getElementById("details-description");
const editRestaurantLink = document.getElementById("edit-restaurant-link");
const menuStatus = document.getElementById("menu-status");
const menuList = document.getElementById("menu-list");

// Ignore responses from requests that a newer request has already replaced.
let listRequest = 0;
let detailsRequest = 0;

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

// Read the selection from the URL. A hand-typed link such as "#/restaurants/%"
// is not valid percent-encoding, so report it instead of letting it throw.
function readSelection() {
  const match = window.location.hash.match(/^#\/restaurants\/(.+)$/);
  if (!match) return { id: null, valid: true };
  try {
    return { id: decodeURIComponent(match[1]), valid: true };
  } catch {
    return { id: null, valid: false };
  }
}

function restaurantHash(restaurantId) {
  return `#/restaurants/${encodeURIComponent(restaurantId)}`;
}

async function loadRestaurants(cuisine) {
  const request = ++listRequest;
  const query = cuisine ? `?cuisine=${encodeURIComponent(cuisine)}` : "";
  setStatus(listStatus, "Loading restaurants…");
  restaurantList.replaceChildren();

  try {
    const restaurants = await getJson(`/restaurants${query}`);
    if (request !== listRequest) return;
    renderRestaurants(restaurants, cuisine);
  } catch (error) {
    if (request !== listRequest) return;
    setStatus(listStatus, `Could not load restaurants: ${error.message}`, true);
  }
}

function renderRestaurants(restaurants, cuisine) {
  if (restaurants.length === 0) {
    setStatus(listStatus, cuisine ? `No restaurants serve "${cuisine}".` : "No restaurants yet.");
    return;
  }

  setStatus(listStatus, cuisine ? `Showing ${cuisine} restaurants.` : "");
  const selectedId = readSelection().id;

  for (const restaurant of restaurants) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "restaurant";
    button.dataset.restaurantId = restaurant.id;
    if (restaurant.id === selectedId) button.setAttribute("aria-current", "true");

    const name = document.createElement("span");
    name.className = "restaurant-name";
    name.textContent = restaurant.name;
    const cuisineLabel = document.createElement("span");
    cuisineLabel.className = "cuisine";
    cuisineLabel.textContent = restaurant.cuisine;
    button.append(name, cuisineLabel);

    button.addEventListener("click", () => {
      const hash = restaurantHash(restaurant.id);
      if (window.location.hash === hash) {
        // Same URL means no hashchange event, so reload directly. This lets a
        // customer retry after an error by clicking the restaurant again.
        showDetails(readSelection());
      } else {
        window.location.hash = hash;
      }
    });

    const item = document.createElement("li");
    item.append(button);
    restaurantList.append(item);
  }
}

function markSelected(restaurantId) {
  for (const button of restaurantList.querySelectorAll("button.restaurant")) {
    if (button.dataset.restaurantId === restaurantId) {
      button.setAttribute("aria-current", "true");
    } else {
      button.removeAttribute("aria-current");
    }
  }
}

async function showDetails(selection) {
  // Every selection change, including clearing it, invalidates older requests,
  // so a slow response can never redisplay a restaurant that is no longer selected.
  const request = ++detailsRequest;
  const restaurantId = selection.id;
  markSelected(restaurantId);
  detailsContent.hidden = true;
  editRestaurantLink.hidden = true;
  editRestaurantLink.removeAttribute("href");

  if (!selection.valid) {
    setStatus(detailsStatus, "That restaurant link isn't valid.", true);
    return;
  }
  if (restaurantId === null) {
    setStatus(detailsStatus, "Select a restaurant to see its details and menu.");
    return;
  }

  const path = `/restaurants/${encodeURIComponent(restaurantId)}`;
  setStatus(detailsStatus, "Loading restaurant…");

  // Start both requests together, but handle them separately: the details are
  // the core requirement, so a menu failure must not hide them.
  const detailsPromise = getJson(path);
  const menuPromise = getJson(`${path}/menu`);
  menuPromise.catch(() => {}); // Handled below; ignored if the details fail first.

  let restaurant;
  try {
    restaurant = await detailsPromise;
  } catch (error) {
    if (request !== detailsRequest) return;
    const message =
      error.status === 404 ? "That restaurant doesn't exist." : `Could not load restaurant: ${error.message}`;
    setStatus(detailsStatus, message, true);
    return;
  }
  if (request !== detailsRequest) return;
  renderRestaurant(restaurant);

  try {
    const menu = await menuPromise;
    if (request !== detailsRequest) return;
    renderMenu(menu);
  } catch (error) {
    if (request !== detailsRequest) return;
    setStatus(menuStatus, `Could not load the menu: ${error.message}`, true);
  }
}

function renderRestaurant(restaurant) {
  detailsName.textContent = restaurant.name;
  detailsCuisine.textContent = restaurant.cuisine;
  detailsDescription.textContent = restaurant.description;
  editRestaurantLink.href = `edit-restaurant.html?id=${encodeURIComponent(restaurant.id)}`;
  editRestaurantLink.hidden = false;
  menuList.replaceChildren();
  setStatus(menuStatus, "Loading menu…");
  setStatus(detailsStatus, "");
  detailsContent.hidden = false;
}

function renderMenu(menu) {
  menuList.replaceChildren();
  if (menu.items.length === 0) {
    setStatus(menuStatus, "This restaurant has no menu items yet.");
    return;
  }
  setStatus(menuStatus, "");
  for (const menuItem of menu.items) {
    const item = document.createElement("li");
    const heading = document.createElement("div");
    heading.className = "menu-item-heading";
    const name = document.createElement("span");
    name.className = "menu-item-name";
    name.textContent = menuItem.name;
    const price = document.createElement("span");
    price.className = "price";
    price.textContent = `$${menuItem.price}`;
    heading.append(name, price);
    const description = document.createElement("p");
    description.textContent = menuItem.description;
    item.append(heading, description);
    menuList.append(item);
  }
}

filterForm.addEventListener("submit", (event) => {
  event.preventDefault();
  // A blank filter is a 422 from the API, so treat it as "show everything".
  loadRestaurants(cuisineInput.value.trim() || null);
});

clearFilter.addEventListener("click", () => {
  cuisineInput.value = "";
  loadRestaurants(null);
});

window.addEventListener("hashchange", () => showDetails(readSelection()));

loadRestaurants(null);
showDetails(readSelection());
