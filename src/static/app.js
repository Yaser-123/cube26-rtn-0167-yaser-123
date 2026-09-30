document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);
    const form = $('returnForm');
    const skuSelect = $('sku');
    const partsInput = $('parts');
    const uploadZone = $('uploadZone');
    const imagePreview = $('imagePreview');
    const submitBtn = $('submitBtn');
    const emptyState = $('emptyState');
    const resultsContent = $('resultsContent');
    const orgSelect = $('orgSelect');
    const recordsBody = $('recordsBody');

    const DECISIONS = {
        restock: ['Restock', 'Put it back into sellable inventory.'],
        refurbish: ['Refurbish', 'Clean, repair or replace a missing part, then resell.'],
        liquidate: ['Liquidate', 'Sell off through a liquidation channel. It is too worn to resell as is.'],
        dispose: ['Dispose', 'Damaged beyond resale. Recycle or destroy it.'],
        pending_review: ['Needs review', 'The agent could not decide safely. A person should check this item.'],
    };
    const CHECK_NAMES = { identity: 'Right item?', completeness: 'Complete?', condition: 'Condition' };

    let catalog = [];
    let uploadedFiles = [];
    let currentRecordId = null;

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text ?? '';
        return div.innerHTML;
    }

    function pill(verdict) {
        return `<span class="pill ${verdict.toLowerCase()}">${verdict}</span>`;
    }

    // Client accounts (tenants)
    const NEW_ACCOUNT = '__new__';
    let activeOrg = localStorage.getItem('org') || 'org_demo_bravo';
    const currentOrg = () => activeOrg;
    const orgName = () => orgSelect.options[orgSelect.selectedIndex]?.text || activeOrg;

    async function loadAccounts() {
        const list = await (await fetch('/api/v1/accounts')).json();
        if (!list.some(a => a.org_id === activeOrg)) activeOrg = list[0].org_id;
        orgSelect.innerHTML = list.map(a => `<option value="${escapeHtml(a.org_id)}">${escapeHtml(a.name)}</option>`).join('')
            + `<option value="${NEW_ACCOUNT}">+ Add client account…</option>`;
        orgSelect.value = activeOrg;
    }

    function switchAccount(org) {
        activeOrg = org;
        localStorage.setItem('org', org);
        orgSelect.value = org;
        // A record from another client must not stay on screen after switching
        resultsContent.classList.add('hidden');
        emptyState.classList.remove('hidden');
        lookupUnit();
        loadExamples();
        loadRecords();
    }

    orgSelect.addEventListener('change', () => {
        if (orgSelect.value === NEW_ACCOUNT) {
            orgSelect.value = activeOrg;
            $('accountName').value = '';
            $('accountForm').classList.remove('hidden');
            $('accountDone').classList.add('hidden');
            $('accountModal').classList.remove('hidden');
            $('accountName').focus();
            return;
        }
        switchAccount(orgSelect.value);
    });

    $('cancelAccountBtn').addEventListener('click', () => $('accountModal').classList.add('hidden'));
    $('closeAccountBtn').addEventListener('click', () => $('accountModal').classList.add('hidden'));
    $('createAccountBtn').addEventListener('click', async () => {
        const name = $('accountName').value.trim();
        if (name.length < 2) { alert('Enter a client name.'); return; }
        const res = await fetch('/api/v1/accounts', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
        });
        if (!res.ok) { alert('Could not create the account.'); return; }
        const account = await res.json();
        await loadAccounts();
        switchAccount(account.org_id);
        $('accountDoneName').textContent = account.name;
        $('accountKey').value = account.api_key;
        $('accountForm').classList.add('hidden');
        $('accountDone').classList.remove('hidden');
    });

    // Guide remembers if it was collapsed
    const guide = $('guide');
    if (localStorage.getItem('guideClosed') === '1') guide.removeAttribute('open');
    guide.addEventListener('toggle', () => localStorage.setItem('guideClosed', guide.open ? '0' : '1'));

    // Catalogue
    async function loadCatalog() {
        const res = await fetch('/api/v1/catalog');
        catalog = res.ok ? await res.json() : [];
        $('skuList').innerHTML = catalog.map(c => `<option value="${escapeHtml(c.sku)}">${escapeHtml(c.description)}</option>`).join('');
    }
    function onSkuChange() {
        const sku = skuSelect.value.trim().toUpperCase();
        const item = catalog.find(c => c.sku === sku);
        if (item) {
            skuSelect.value = item.sku;
            partsInput.value = item.parts;
            $('skuDesc').textContent = item.description;
        } else {
            $('skuDesc').textContent = sku ? 'Not in the catalogue. The item will be sent for review, since identity cannot be confirmed.' : '';
        }
    }
    skuSelect.addEventListener('input', onSkuChange);
    skuSelect.addEventListener('change', onSkuChange);

    // Unit ID -> original order
    let currentOrder = null;
    let lookupTimer = null;
    const unitInput = $('unitId');
    const unitHint = $('unitHint');
    const DEFAULT_UNIT_HINT = unitHint.textContent;

    async function loadExamples() {
        const res = await fetch('/api/v1/orders', { headers: { 'x-org-id': currentOrg() } });
        const examples = res.ok ? (await res.json()).examples : [];
        unitInput.placeholder = examples.length ? `e.g. ${examples.slice(0, 3).join(', ')}` : 'e.g. UNIT-0001';
    }

    async function lookupUnit() {
        const unit = unitInput.value.trim();
        currentOrder = null;
        unitHint.style.color = '';
        if (!unit) { unitHint.textContent = DEFAULT_UNIT_HINT; return; }
        const res = await fetch(`/api/v1/orders/${encodeURIComponent(unit)}`, { headers: { 'x-org-id': currentOrg() } });
        if (unit !== unitInput.value.trim()) return;  // user kept typing
        if (res.ok) {
            currentOrder = await res.json();
            skuSelect.value = currentOrder.ordered_sku;
            onSkuChange();
            partsInput.value = currentOrder.parts_list;
            unitHint.textContent = `✓ Order ${currentOrder.order_id} found. Product and parts filled in.`;
            unitHint.style.color = 'var(--ok)';
        } else {
            unitHint.textContent = `No order on file for this unit in ${orgName()}. Enter the product yourself.`;
        }
    }
    unitInput.addEventListener('input', () => {
        clearTimeout(lookupTimer);
        lookupTimer = setTimeout(lookupUnit, 300);
    });

    // Photos
    ['dragenter', 'dragover'].forEach(ev => uploadZone.addEventListener(ev, e => { e.preventDefault(); uploadZone.classList.add('dragover'); }));
    ['dragleave', 'drop'].forEach(ev => uploadZone.addEventListener(ev, e => { e.preventDefault(); uploadZone.classList.remove('dragover'); }));
    uploadZone.addEventListener('drop', e => handleFiles(e.dataTransfer.files));
    $('fileInput').addEventListener('change', function () { handleFiles(this.files); this.value = ''; });
    $('cameraBtn').addEventListener('click', () => $('cameraInput').click());
    $('cameraInput').addEventListener('change', function () { handleFiles(this.files, true); this.value = ''; });
    $('clearBtn').addEventListener('click', () => { uploadedFiles = []; renderPreviews(); });

    function handleFiles(files, append = false) {
        const images = Array.from(files).filter(f => f.type.startsWith('image/'));
        uploadedFiles = (append ? uploadedFiles.concat(images) : images).slice(0, 3);
        renderPreviews();
    }
    function renderPreviews() {
        imagePreview.innerHTML = '';
        uploadedFiles.forEach(file => {
            const img = document.createElement('img');
            img.src = URL.createObjectURL(file);
            img.alt = file.name;
            img.title = file.name;
            imagePreview.appendChild(img);
        });
    }

    function downscaleImage(file, maxEdge) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                const scale = Math.min(1, maxEdge / Math.max(img.width, img.height));
                const canvas = document.createElement('canvas');
                canvas.width = Math.round(img.width * scale);
                canvas.height = Math.round(img.height * scale);
                canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
                URL.revokeObjectURL(img.src);
                resolve(canvas.toDataURL('image/jpeg', 0.85));
            };
            img.onerror = reject;
            img.src = URL.createObjectURL(file);
        });
    }

    // Inspect
    form.addEventListener('submit', async e => {
        e.preventDefault();
        if (uploadedFiles.length === 0) {
            alert('Add at least one photo of the returned item.');
            return;
        }
        submitBtn.classList.add('loading');
        submitBtn.disabled = true;
        $('submitLabel').textContent = 'Inspecting… (about 10 seconds)';
        try {
            // Downscaled in the browser so phone photos upload fast; 1024px matches what the model sees
            const photoRefs = await Promise.all(uploadedFiles.map(f => downscaleImage(f, 1024)));
            const response = await fetch('/api/v1/returns/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'x-org-id': currentOrg() },
                body: JSON.stringify({
                    unit_id: $('unitId').value,
                    organization_id: currentOrg(),
                    operator_label: 'op_demo',
                    order_id: currentOrder?.order_id || 'N/A',
                    ordered_asin: currentOrder?.ordered_asin || null,
                    ordered_sku: skuSelect.value.trim().toUpperCase(),
                    parts_list: partsInput.value,
                    photo_refs: photoRefs,
                }),
            });
            const data = await response.json();
            if (!response.ok) {
                const detail = Array.isArray(data.detail)
                    ? data.detail.map(d => `${d.loc[d.loc.length - 1]}: ${d.msg}`).join('\n')
                    : data.detail;
                alert(`Please check the form:\n${detail}`);
                return;
            }
            renderResults(data);
            loadRecords();
        } catch (error) {
            console.error(error);
            alert('Could not reach the server. Is it running?');
        } finally {
            submitBtn.classList.remove('loading');
            submitBtn.disabled = false;
            $('submitLabel').textContent = 'Inspect return';
        }
    });

    function renderResults(data) {
        currentRecordId = data.record_id;
        emptyState.classList.add('hidden');
        resultsContent.classList.remove('hidden');

        const [label, help] = DECISIONS[data.outcome] || [data.outcome, ''];
        const badge = $('dispositionBadge');
        badge.textContent = label;
        badge.className = `decision-value ${data.outcome}`;
        $('dispositionHelp').textContent = help;

        const notes = [];
        if (data.outcome === 'pending_review') {
            const reasons = data.checks
                .filter(c => c.verdict === 'UNCERTAIN' || (c.check_key === 'identity' && c.verdict === 'FAIL'))
                .map(c => c.verdict === 'UNCERTAIN'
                    ? `${CHECK_NAMES[c.check_key].replace('?', '').toLowerCase()} couldn't be confirmed from the photos`
                    : "the item doesn't match the ordered product");
            if (reasons.length) {
                notes.push(`<div class="note warn"><b>Why it needs review:</b> ${escapeHtml(reasons.join('; '))}. Try clearer photos of the item out of its packaging, or decide manually.</div>`);
            }
        }
        (data.overrides || []).forEach(o => {
            notes.push(`<div class="note info"><b>Changed by ${escapeHtml(o.operator)}:</b> ${escapeHtml((DECISIONS[o.original_verdict] || [o.original_verdict])[0])} → ${escapeHtml((DECISIONS[o.revised_verdict] || [o.revised_verdict])[0])}. Reason: ${escapeHtml(o.reason)}</div>`);
        });
        $('notes').innerHTML = notes.join('');

        $('checksGrid').innerHTML = data.checks.map(c => `
            <div class="check">
                <div>
                    <h4>${escapeHtml(CHECK_NAMES[c.check_key] || c.check_key)}</h4>
                    <p>${escapeHtml(c.detail)}</p>
                    <div class="conf">Confidence ${(c.confidence * 100).toFixed(0)}%</div>
                </div>
                <div>${pill(c.verdict)}</div>
            </div>`).join('');

        $('recordId').textContent = data.record_id;
        $('capturedAt').textContent = new Date(data.captured_at).toLocaleString();
        $('modelVersion').textContent = data.checks[0]?.model_version || '';
        $('contentHash').textContent = data.content_hash;
        $('jsonView').textContent = JSON.stringify(data, null, 2);
    }

    // History
    async function loadRecords() {
        $('recordsOrg').textContent = orgName();
        const response = await fetch('/api/v1/returns', { headers: { 'x-org-id': currentOrg() } });
        const records = response.ok ? await response.json() : [];
        if (!records.length) {
            recordsBody.innerHTML = '<tr><td colspan="7" class="muted">No inspections for this client yet.</td></tr>';
            return;
        }
        const verdict = (r, key) => {
            const c = r.checks.find(c => c.check_key === key);
            return c ? pill(c.verdict) : '';
        };
        recordsBody.innerHTML = records.slice().reverse().map(r => `
            <tr class="clickable" data-id="${escapeHtml(r.record_id)}">
                <td>${escapeHtml(new Date(r.captured_at).toLocaleString())}</td>
                <td>${escapeHtml(r.subject)}</td>
                <td>${verdict(r, 'identity')}</td>
                <td>${verdict(r, 'completeness')}</td>
                <td>${verdict(r, 'condition')}</td>
                <td><span class="pill ${escapeHtml(r.outcome)}">${escapeHtml((DECISIONS[r.outcome] || [r.outcome])[0])}</span>${r.overrides.length ? ' <span class="muted small">(changed)</span>' : ''}</td>
                <td class="mono muted">${escapeHtml(r.record_id)}</td>
            </tr>`).join('');
        recordsBody.querySelectorAll('tr.clickable').forEach(row => row.addEventListener('click', async () => {
            const res = await fetch(`/api/v1/returns/${encodeURIComponent(row.dataset.id)}`, { headers: { 'x-org-id': currentOrg() } });
            if (res.ok) {
                renderResults(await res.json());
                $('resultsPanel').scrollIntoView({ behavior: 'smooth' });
            }
        }));
    }

    // Change decision
    const overrideModal = $('overrideModal');
    $('overrideBtn').addEventListener('click', () => { $('overrideReason').value = ''; overrideModal.classList.remove('hidden'); });
    $('cancelOverrideBtn').addEventListener('click', () => overrideModal.classList.add('hidden'));
    $('submitOverrideBtn').addEventListener('click', async () => {
        const reason = $('overrideReason').value.trim();
        if (reason.length < 3) {
            alert('Please give a short reason for the change.');
            return;
        }
        const btn = $('submitOverrideBtn');
        btn.disabled = true;
        try {
            const response = await fetch(`/api/v1/returns/${encodeURIComponent(currentRecordId)}/override`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'x-org-id': currentOrg() },
                body: JSON.stringify({ revised_verdict: $('overrideVerdict').value, reason }),
            });
            if (!response.ok) throw new Error(await response.text());
            renderResults(await response.json());
            loadRecords();
            overrideModal.classList.add('hidden');
        } catch (error) {
            console.error(error);
            alert('Could not save the change.');
        } finally {
            btn.disabled = false;
        }
    });

    (async () => {
        await Promise.all([loadCatalog(), loadAccounts()]);
        loadExamples();
        loadRecords();
    })();
});
