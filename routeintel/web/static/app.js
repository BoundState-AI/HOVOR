const API_BASE = '/api/v1';

const tripSelect = document.getElementById('tripSelect');
const radiusInput = document.getElementById('radiusInput');
const loadButton = document.getElementById('loadButton');
const tripInfo = document.getElementById('tripInfo');
const resultsContainer = document.getElementById('resultsContainer');

async function fetchTrips() {
    try {
        const response = await fetch(`${API_BASE}/trips`);
        const trips = await response.json();

        tripSelect.innerHTML = '<option value="">Select a trip...</option>';

        trips.forEach(trip => {
            const option = document.createElement('option');
            option.value = trip.id;
            const date = new Date(trip.started_at).toLocaleDateString();
            const purpose = trip.purpose || 'No purpose';
            option.textContent = `Trip #${trip.id} - ${date} - ${purpose}`;
            tripSelect.appendChild(option);
        });
    } catch (error) {
        showError('Failed to load trips: ' + error.message);
    }
}

async function loadTripLeads() {
    const tripId = tripSelect.value;
    const radius = radiusInput.value || 20;

    if (!tripId) return;

    loadButton.disabled = true;
    resultsContainer.innerHTML = '<div class="loading">Loading lead data...</div>';

    try {
        const [tripResponse, leadsResponse] = await Promise.all([
            fetch(`${API_BASE}/trips/${tripId}`),
            fetch(`${API_BASE}/trips/${tripId}/lead_view?radius_km=${radius}`)
        ]);

        const trip = await tripResponse.json();
        const leads = await leadsResponse.json();

        displayTripInfo(trip);
        displayLeads(leads);
    } catch (error) {
        showError('Failed to load lead data: ' + error.message);
    } finally {
        loadButton.disabled = false;
    }
}

function displayTripInfo(trip) {
    const startDate = new Date(trip.started_at).toLocaleString();
    const endDate = trip.ended_at ? new Date(trip.ended_at).toLocaleString() : 'In Progress';

    tripInfo.style.display = 'block';
    tripInfo.innerHTML = `
        <div class="trip-info">
            <h2>Trip Summary</h2>
            <p><strong>Trip ID:</strong> ${trip.id}</p>
            <p><strong>User:</strong> ${trip.user_id}</p>
            <p><strong>Purpose:</strong> ${trip.purpose || 'N/A'}</p>
            <p><strong>Started:</strong> ${startDate}</p>
            <p><strong>Ended:</strong> ${endDate}</p>
            <p><strong>Status:</strong> ${trip.status}</p>
            <p><strong>Distance:</strong> ${trip.total_distance_km.toFixed(2)} km</p>
        </div>
    `;
}

function displayLeads(leads) {
    if (leads.length === 0) {
        resultsContainer.innerHTML = '<div class="info">No companies found near this route.</div>';
        return;
    }

    let html = `
        <h2>Nearby Companies (${leads.length} found)</h2>
        <table>
            <thead>
                <tr>
                    <th>Company Name</th>
                    <th>City/State</th>
                    <th>Industry</th>
                    <th>Employees</th>
                    <th>Status</th>
                    <th>Last Contact</th>
                </tr>
            </thead>
            <tbody>
    `;

    leads.forEach(lead => {
        const company = lead.company;
        const location = [company.city, company.state].filter(x => x).join(', ') || 'N/A';
        const lastContact = lead.last_contacted_at
            ? new Date(lead.last_contacted_at).toLocaleDateString()
            : 'Never';
        const statusClass = `status-${lead.lead_status.toLowerCase()}`;

        html += `
            <tr>
                <td><strong>${company.name}</strong></td>
                <td>${location}</td>
                <td>${company.industry || 'N/A'}</td>
                <td>${company.employee_count || 'N/A'}</td>
                <td><span class="status-badge ${statusClass}">${lead.lead_status}</span></td>
                <td>${lastContact}</td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    resultsContainer.innerHTML = html;
}

function showError(message) {
    resultsContainer.innerHTML = `<div class="error">${message}</div>`;
}

tripSelect.addEventListener('change', () => {
    loadButton.disabled = !tripSelect.value;
    tripInfo.style.display = 'none';
    resultsContainer.innerHTML = '';
});

loadButton.addEventListener('click', loadTripLeads);

fetchTrips();
