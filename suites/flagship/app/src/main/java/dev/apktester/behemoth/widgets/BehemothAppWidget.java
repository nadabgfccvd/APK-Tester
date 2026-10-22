package dev.apktester.behemoth.widgets;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.widget.RemoteViews;

import dev.apktester.behemoth.R;

/**
 * App widget principal do Behemoth (receiver declarado no manifesto com o
 * meta-data android.appwidget.provider -> res/xml/appwidget_provider.xml).
 *
 * onUpdate reescreve cada instancia com o layout widget_behemoth e o rotulo
 * app_name (string gerada pelo gen-strings).
 */
public class BehemothAppWidget extends AppWidgetProvider {

    @Override
    public void onUpdate(Context context, AppWidgetManager appWidgetManager,
            int[] appWidgetIds) {
        for (int appWidgetId : appWidgetIds) {
            RemoteViews views = new RemoteViews(context.getPackageName(),
                    R.layout.widget_behemoth);
            views.setTextViewText(R.id.widget_text,
                    context.getString(R.string.app_name));
            appWidgetManager.updateAppWidget(appWidgetId, views);
        }
    }
}
