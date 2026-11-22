import { useEffect, useRef, useState } from 'react'
import { arUrl, loadArModel } from '../data.js'
import { useNarrow } from '../useNarrow.js'
import './ARView.css'

// "View in AR": a static 3D model of the fire area, built by tools/build_ar_model.py into public/ar/.
// model-viewer (with three.js) is large, so it is loaded only when someone opens the viewer. On Android the
// AR button hands over to WebXR or Scene Viewer, on iPhone and iPad to AR Quick Look (the .usdz); on a laptop
// the viewer is a 3D preview to turn with the mouse.
export default function ARView() {
  const [model, setModel] = useState(null)
  const [state, setState] = useState('closed')   // closed | loading | open | error
  const [canAr, setCanAr] = useState(null)
  const [arFailed, setArFailed] = useState(false)
  const dialog = useRef(null)
  const viewer = useRef(null)
  const narrow = useNarrow()   // portrait phone: let model-viewer frame the whole block

  useEffect(() => { loadArModel().then(setModel) }, [])

  useEffect(() => {
    const v = viewer.current
    if (state !== 'open' || !v) return
    const onLoad = () => setCanAr(Boolean(v.canActivateAR))
    const onStatus = (e) => setArFailed(e.detail.status === 'failed')
    v.addEventListener('load', onLoad)
    v.addEventListener('ar-status', onStatus)
    return () => {
      v.removeEventListener('load', onLoad)
      v.removeEventListener('ar-status', onStatus)
    }
  }, [state])

  if (!model) return null   // the model has not been built: no button

  const open = async () => {
    setState('loading')
    dialog.current.showModal()
    try {
      await import('@google/model-viewer')
      setState('open')
    } catch {
      setState('error')
    }
  }

  return (
    <>
      <button type="button" className="ar-open" onClick={open}>View the fire area in 3D and AR</button>
      <dialog ref={dialog} className="ar-dialog" aria-label="3D model of the fire area"
        onClose={() => { setState('closed'); setCanAr(null); setArFailed(false) }}>
        <header>
          <strong>{model.title}</strong>
          <button type="button" className="ar-close" onClick={() => dialog.current.close()} aria-label="Close">×</button>
        </header>
        <div className="ar-stage">
          {state === 'loading' && <p className="ar-msg">Loading the 3D viewer…</p>}
          {state === 'error' && <p className="ar-msg">The 3D viewer could not be loaded. Check the connection and try again.</p>}
          {state === 'open' && (
            <model-viewer ref={viewer} src={arUrl(model.glb)} ios-src={model.usdz ? arUrl(model.usdz) : undefined}
              alt={`3D model of the Burgohondo fire area: terrain with burn severity, streams and towns coloured by risk`}
              ar ar-modes="webxr scene-viewer quick-look" ar-placement="floor" ar-scale="auto"
              camera-controls="" touch-action="pan-y" camera-orbit={narrow ? '0deg 50deg auto' : '0deg 50deg 70%'} exposure="0.8" shadow-intensity="1">
              <button type="button" slot="ar-button" className="ar-place">Place it on your desk or floor</button>
            </model-viewer>
          )}
        </div>
        <p className="ar-note">
          About {Math.round(model.width_cm)} × {Math.round(model.depth_cm)} cm at real size, so it fits on a table.
          Relief exaggerated {model.exaggeration}×. It shows one moment, after the fire (data export
          of {model.data_generated.slice(0, 10)}), and does not follow the story.
          {canAr === false && ' To place it in the room, open this page on an Android phone or an iPhone.'}
          {arFailed && ' AR did not start on this device; the 3D view still works.'}
        </p>
      </dialog>
    </>
  )
}
