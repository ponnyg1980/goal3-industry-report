<?php
/**
 * Plugin Name:  TMH Industry Trademark Report
 * Description:  Native industry trademark report pages for The Trademark Helpline.
 *               Renders the report via a shortcode and proxies the report engine
 *               API first-party, so nothing depends on CORS and the upstream
 *               host URL is never exposed to the browser.
 * Version:      1.0.0
 * Author:       The Trademark Helpline
 * License:      Proprietary
 *
 * HOW IT FITS TOGETHER
 *   Browser → /wp-json/tmh/v1/<path>   (this plugin, same origin)
 *           → PYTHON ENGINE            (Render / Cloud Run — set in Settings)
 *
 * The Python engine is the finished report logic (Temmy queries, banding,
 * viability, SIC naming). WordPress can't run Python, so the engine is hosted
 * separately; this plugin is the first-party front door to it. Swapping hosts,
 * or moving to api.thetrademarkhelpline.com later, is a one-field change in
 * Settings → TMH Report — the page never changes.
 *
 * USAGE
 *   1. Install & activate this plugin.
 *   2. Settings → TMH Report → paste the engine URL (e.g. the Render URL).
 *   3. Put [tmh_industry_report] on any page (e.g. /industry-report/).
 */

if (!defined('ABSPATH')) { exit; }

define('TMH_REPORT_VER', '1.0.0');
define('TMH_REPORT_OPT', 'tmh_report_engine_url');

/* ------------------------------------------------------------------ */
/*  1. Settings — where the Python engine lives                        */
/* ------------------------------------------------------------------ */

add_action('admin_menu', function () {
    add_options_page(
        'TMH Report', 'TMH Report', 'manage_options', 'tmh-report',
        'tmh_report_settings_page');
});

add_action('admin_init', function () {
    register_setting('tmh_report', TMH_REPORT_OPT, [
        'type' => 'string',
        'sanitize_callback' => 'esc_url_raw',
        'default' => '',
    ]);
});

function tmh_report_settings_page() {
    if (!current_user_can('manage_options')) { return; }
    $url = get_option(TMH_REPORT_OPT, '');
    ?>
    <div class="wrap">
      <h1>TMH Industry Trademark Report</h1>
      <p>The report engine (the Python API) runs on its own host. Paste its
         base URL below — the <code>.onrender.com</code> / <code>.run.app</code>
         address is fine; it does not have to be a subdomain. The browser never
         sees it: calls go through <code>/wp-json/tmh/v1/…</code> on this site.</p>
      <form method="post" action="options.php">
        <?php settings_fields('tmh_report'); ?>
        <table class="form-table">
          <tr>
            <th scope="row"><label for="tmh_url">Engine URL</label></th>
            <td>
              <input name="<?php echo esc_attr(TMH_REPORT_OPT); ?>" id="tmh_url"
                     type="url" class="regular-text"
                     placeholder="https://tmh-report-api.onrender.com"
                     value="<?php echo esc_attr($url); ?>">
              <p class="description">Then add the shortcode
                 <code>[tmh_industry_report]</code> to a page.</p>
            </td>
          </tr>
        </table>
        <?php submit_button(); ?>
      </form>
      <?php if ($url): ?>
        <h2>Connection</h2>
        <?php
          $health = wp_remote_get(trailingslashit($url) . 'health',
                                  ['timeout' => 8]);
          if (is_wp_error($health)) {
              echo '<p style="color:#b32d2e">Could not reach the engine: '
                   . esc_html($health->get_error_message()) . '</p>';
          } else {
              $code = wp_remote_retrieve_response_code($health);
              $body = wp_remote_retrieve_body($health);
              echo '<p><strong>GET /health</strong> → ' . intval($code)
                   . ' <code>' . esc_html($body) . '</code></p>';
          }
        ?>
      <?php endif; ?>
    </div>
    <?php
}

/* ------------------------------------------------------------------ */
/*  2. First-party proxy:  /wp-json/tmh/v1/<path>  →  engine/<path>    */
/* ------------------------------------------------------------------ */

add_action('rest_api_init', function () {
    register_rest_route('tmh/v1', '/(?P<path>.+)', [
        'methods'  => ['GET', 'POST'],
        'permission_callback' => '__return_true',   // public report, read-only
        'callback' => 'tmh_report_proxy',
    ]);
});

function tmh_report_proxy(WP_REST_Request $req) {
    $base = get_option(TMH_REPORT_OPT, '');
    if (!$base) {
        return new WP_REST_Response(['error' => 'engine URL not configured'], 503);
    }
    // Only forward known engine endpoints — never an open relay.
    $path = ltrim($req['path'], '/');
    $allowed = ['find', 'owner-marks', 'company', 'sector', 'classes',
                'terms', 'viability', 'assessment', 'business-types', 'health'];
    $first = explode('/', $path)[0];
    if (!in_array($first, $allowed, true)) {
        return new WP_REST_Response(['error' => 'unknown endpoint'], 404);
    }

    $qs  = $req->get_query_params();
    unset($qs['path'], $qs['rest_route']);
    $url = trailingslashit($base) . $path;
    if ($qs) { $url .= '?' . http_build_query($qs); }

    $args = ['timeout' => 30, 'headers' => ['Accept' => 'application/json']];
    if (strtoupper($req->get_method()) === 'POST') {
        $args['method']  = 'POST';
        $args['headers']['Content-Type'] = 'application/json';
        $args['body']    = $req->get_body();
        $resp = wp_remote_post($url, $args);
    } else {
        $resp = wp_remote_get($url, $args);
    }

    if (is_wp_error($resp)) {
        return new WP_REST_Response(
            ['error' => $resp->get_error_message()], 502);
    }
    $code = wp_remote_retrieve_response_code($resp);
    $body = wp_remote_retrieve_body($resp);
    $out  = new WP_REST_Response(json_decode($body, true), $code ?: 200);
    // Short cache: the same company within a session shouldn't re-hit Temmy.
    $out->header('Cache-Control', 'public, max-age=300');
    return $out;
}

/* ------------------------------------------------------------------ */
/*  3. The page itself — [tmh_industry_report]                         */
/* ------------------------------------------------------------------ */

add_shortcode('tmh_industry_report', function () {
    $assets = plugins_url('assets', __FILE__);

    wp_enqueue_style('tmh-fonts',
        'https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600;700;800&display=swap',
        [], null);
    wp_enqueue_style('tmh-braudit', $assets . '/braudit.css', [], TMH_REPORT_VER);
    wp_enqueue_script('tmh-report', $assets . '/report.js', [], TMH_REPORT_VER, true);

    // Hand the front end its two config values. API base is THIS site's proxy,
    // so every call is first-party — no CORS, upstream host hidden.
    wp_localize_script('tmh-report', 'TMH_CONFIG', [
        'api'    => esc_url_raw(rest_url('tmh/v1')),
        'assets' => esc_url_raw($assets),
    ]);

    // The container the script renders into (matches web/report.html).
    return '<div id="tmh-report" class="bd"><div class="tmh-wrap">'
         . '<div class="between tmh-head">'
         .   '<div class="row" style="gap:12px;align-items:center">'
         .     '<img id="tmh-logo" alt="The Trademark Helpline" style="height:34px">'
         .     '<span class="muted" id="tmh-subject"></span></div>'
         .   '<span class="eyebrow" id="tmh-stage">Free sector report</span></div>'
         . '<section id="scr-input" class="tmh-screen"></section>'
         . '<section id="scr-build" class="tmh-screen" hidden></section>'
         . '<section id="scr-reveal1" class="tmh-screen" hidden></section>'
         . '</div></div>';
});
