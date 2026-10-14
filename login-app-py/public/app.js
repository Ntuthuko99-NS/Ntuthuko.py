const $ = (id) => document.getElementById(id);
let mode = 'login'; // 'login' | 'register'

async function api(path, options = {}) {
  const res = await fetch(path, {
    method: options.method || 'GET',
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Something went wrong. Try again.');
  return data;
}

function setMode(next) {
  mode = next;
  const register = mode === 'register';
  $('auth-title').textContent = register ? 'Create an account' : 'Log in';
  $('auth-submit').textContent = register ? 'Create account' : 'Log in';
  $('switch-text').textContent = register ? 'Already have an account?' : 'New here?';
  $('switch-btn').textContent = register ? 'Log in' : 'Create an account';
  $('name-field').hidden = !register;
  $('auth-form').password.autocomplete = register ? 'new-password' : 'current-password';
  $('auth-error').textContent = '';
}

function showAuth() {
  $('home').hidden = true;
  $('auth').hidden = false;
  setMode('login');
}

async function showHome(user) {
  $('auth').hidden = true;
  $('home').hidden = false;
  $('welcome').textContent = `Hi, ${user.name}`;
  $('member-since').textContent = `Member since ${new Date(user.createdAt.replace(' ', 'T') + 'Z').toLocaleDateString()}`;
  await loadNotes();
}

async function loadNotes() {
  const { notes } = await api('/api/notes');
  const list = $('notes');
  list.replaceChildren();
  $('empty').hidden = notes.length > 0;
  for (const n of notes) {
    const li = document.createElement('li');
    const text = document.createElement('div');
    text.textContent = n.body; // textContent avoids XSS
    const small = document.createElement('small');
    small.textContent = new Date(n.createdAt.replace(' ', 'T') + 'Z').toLocaleString();
    text.append(small);
    const del = document.createElement('button');
    del.type = 'button';
    del.textContent = 'Delete';
    del.addEventListener('click', async () => {
      await api(`/api/notes/${n.id}`, { method: 'DELETE' });
      loadNotes();
    });
    li.append(text, del);
    list.append(li);
  }
}

$('switch-btn').addEventListener('click', () => setMode(mode === 'login' ? 'register' : 'login'));

$('auth-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target;
  const btn = $('auth-submit');
  btn.disabled = true;
  $('auth-error').textContent = '';
  try {
    const body = { email: f.email.value, password: f.password.value };
    if (mode === 'register') body.name = f.name.value;
    const { user } = await api(mode === 'register' ? '/api/register' : '/api/login', { method: 'POST', body });
    f.reset();
    await showHome(user);
  } catch (err) {
    $('auth-error').textContent = err.message;
  } finally {
    btn.disabled = false;
  }
});

$('note-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('note-error').textContent = '';
  try {
    await api('/api/notes', { method: 'POST', body: { body: $('note-body').value } });
    $('note-body').value = '';
    await loadNotes();
  } catch (err) {
    $('note-error').textContent = err.message;
  }
});

$('logout').addEventListener('click', async () => {
  await api('/api/logout', { method: 'POST' });
  showAuth();
});

(async () => {
  try {
    const { user } = await api('/api/me');
    user ? await showHome(user) : showAuth();
  } catch {
    showAuth();
  }
})();
