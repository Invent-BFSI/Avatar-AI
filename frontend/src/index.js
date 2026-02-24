import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.js';

// This is the entry point that hooks your App.js into the HTML
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
