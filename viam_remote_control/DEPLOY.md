# Deploy Gus Remote Control

## 1. Rotate Viam Credentials

The previous Viam API key was stored in source code while developing locally. Before making the project public, create a new Viam API key and revoke the old one.

## 2. Deploy Backend on Render

Create a Render Web Service from this Git repository.

Use these settings:

```text
Root Directory: viam_remote_control
Build Command: pip install -r requirements.txt
Start Command: cd backend && uvicorn app:app --host 0.0.0.0 --port $PORT
```

Add these Render environment variables:

```text
VIAM_ADDRESS=your-machine-address.viam.cloud
VIAM_API_KEY=your-new-viam-api-key
VIAM_API_KEY_ID=your-viam-api-key-id
CONTROL_TOKEN=choose-a-passcode-for-the-web-ui
```

After deploy, test:

```text
https://your-render-service.onrender.com/
https://your-render-service.onrender.com/diagnostics?token=YOUR_CONTROL_TOKEN
```

## 3. Deploy Frontend on Vercel

Create a Vercel project from the same Git repository.

Use these settings:

```text
Root Directory: viam_remote_control/frontend
Framework Preset: Vite
Build Command: npm run build
Output Directory: dist
```

Add this Vercel environment variable:

```text
VITE_API_BASE_URL=https://your-render-service.onrender.com
```

Redeploy after adding the variable.

## 4. Use the Public URL

Open the Vercel URL, enter the same `CONTROL_TOKEN` passcode in the UI, and test camera, movement, stop, and capture.
