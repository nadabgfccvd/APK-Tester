package dev.apktester.behemoth;

import android.content.Context;
import android.opengl.GLES31;
import android.opengl.GLSurfaceView;
import android.os.SystemClock;
import dev.apktester.behemoth.probe.ProbeCatalog;
import dev.apktester.behemoth.probe.ProbeReporter;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.List;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Renderer dos probes GLES 3.1 da shader-library (classe carregada
 * apenas com SDK >= 21 — guardada por GlesProbeActivity).
 *
 * Para CADA programa de assets/shader-library/index.json:
 *   glCreateShader -> glShaderSource -> glCompileShader -> glGetShaderiv
 *   (link com glCreateProgram/glAttachShader/glLinkProgram/glGetProgramiv)
 * e acumula resultado estruturado {id, stage, compiled, linked, log}.
 *
 * A LEI: qualquer falha (shader 0, compile/link error, JSONException,
 * ausencia de GLES) vira registro estruturado via ProbeReporter — nunca
 * excecao propagada, nunca crash. Sob o RustyDroid as chamadas de GLES
 * nao existem: o resultado estruturado documentara o erro (NOT_IMPLEMENTED
 * classificavel), que e exatamente o comportamento exigido do golden.
 */
final class GlesShaderLibraryRenderer implements GLSurfaceView.Renderer {

    private final Context context;
    private final long startedAt;
    private boolean recorded;

    GlesShaderLibraryRenderer(Context context, long startedAt) {
        this.context = context;
        this.startedAt = startedAt;
    }

    @Override
    public void onSurfaceCreated(GL10 gl, EGLConfig config) {
        if (recorded) {
            return;
        }
        recorded = true;
        int programs = 0;
        int compiled = 0;
        int linked = 0;
        String error = null;
        List<String> failures = new ArrayList<String>();
        try {
            JSONObject index = new JSONObject(readAsset("shader-library/index.json"));
            JSONArray entries = index.getJSONArray("programs");
            programs = entries.length();
            for (int i = 0; i < entries.length(); i++) {
                JSONObject program = entries.getJSONObject(i);
                String id = program.getString("id");
                String stage = program.optString("stage", "graphics");
                JSONArray files = program.getJSONArray("files");
                int vertShader = 0;
                int fragShader = 0;
                int compShader = 0;
                int programHandle = 0;
                try {
                    if ("compute".equals(stage)) {
                        String src = readAsset(files.getString(0));
                        compShader = compileShader(GLES31.GL_COMPUTE_SHADER, src);
                        if (compShader != 0) {
                            compiled++;
                            programHandle = GLES31.glCreateProgram();
                            GLES31.glAttachShader(programHandle, compShader);
                            GLES31.glLinkProgram(programHandle);
                            int[] status = new int[1];
                            GLES31.glGetProgramiv(programHandle,
                                    GLES31.GL_LINK_STATUS, status, 0);
                            if (status[0] != 0) {
                                linked++;
                            } else {
                                failures.add(id + ":link");
                            }
                        } else {
                            failures.add(id + ":compile");
                        }
                    } else {
                        String vsrc = readAsset(files.getString(0));
                        String fsrc = readAsset(files.getString(1));
                        vertShader = compileShader(GLES31.GL_VERTEX_SHADER, vsrc);
                        fragShader = compileShader(GLES31.GL_FRAGMENT_SHADER, fsrc);
                        if (vertShader != 0 && fragShader != 0) {
                            compiled++;
                            programHandle = GLES31.glCreateProgram();
                            GLES31.glAttachShader(programHandle, vertShader);
                            GLES31.glAttachShader(programHandle, fragShader);
                            GLES31.glLinkProgram(programHandle);
                            int[] status = new int[1];
                            GLES31.glGetProgramiv(programHandle,
                                    GLES31.GL_LINK_STATUS, status, 0);
                            if (status[0] != 0) {
                                linked++;
                            } else {
                                failures.add(id + ":link");
                            }
                        } else {
                            failures.add(id + ":compile");
                        }
                    }
                } catch (Exception inner) {
                    failures.add(id + ":" + inner.getClass().getSimpleName());
                } finally {
                    if (vertShader != 0) {
                        GLES31.glDeleteShader(vertShader);
                    }
                    if (fragShader != 0) {
                        GLES31.glDeleteShader(fragShader);
                    }
                    if (compShader != 0) {
                        GLES31.glDeleteShader(compShader);
                    }
                    if (programHandle != 0) {
                        GLES31.glDeleteProgram(programHandle);
                    }
                }
            }
        } catch (Throwable t) { // lei do probe: erro estruturado, nunca crash
            error = t.getClass().getSimpleName() + ": " + t.getMessage();
        }
        boolean ok = error == null && programs > 0 && linked == programs;
        String detail = ok
                ? programs + " programas: " + compiled + " compilados, "
                        + linked + " linkados (GLES 3.1 real)"
                : (error != null ? error
                        : "link " + linked + "/" + programs
                                + "; falhas: " + failures.subList(0,
                                Math.min(8, failures.size())));
        ProbeReporter.record(context, ProbeCatalog.MEDIA_GX_001, ok,
                ok ? null : detail, SystemClock.uptimeMillis() - startedAt);
    }

    private int compileShader(int type, String source) {
        int shader = GLES31.glCreateShader(type);
        if (shader == 0) {
            return 0;
        }
        GLES31.glShaderSource(shader, source);
        GLES31.glCompileShader(shader);
        int[] status = new int[1];
        GLES31.glGetShaderiv(shader, GLES31.GL_COMPILE_STATUS, status, 0);
        if (status[0] == 0) {
            GLES31.glDeleteShader(shader);
            return 0;
        }
        return shader;
    }

    private String readAsset(String path) throws Exception {
        BufferedReader reader = new BufferedReader(new InputStreamReader(
                context.getAssets().open(path), "UTF-8"));
        StringBuilder sb = new StringBuilder(1 << 14);
        try {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line).append('\n');
            }
        } finally {
            reader.close();
        }
        return sb.toString();
    }

    @Override
    public void onSurfaceChanged(GL10 gl, int width, int height) {
        // probes nao desenham: apenas compilam/linkam (resultado estruturado)
    }

    @Override
    public void onDrawFrame(GL10 gl) {
        // probes nao desenham: apenas compilam/linkam (resultado estruturado)
    }
}
