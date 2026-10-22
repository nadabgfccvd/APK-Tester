package dev.apktester.behemoth.widgets;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.widget.RemoteViews;

/**
 * Segundo app widget do Behemoth (receiver declarado no manifesto com o
 * meta-data android.appwidget.provider ->
 * res/xml/appwidget_provider_second.xml e o rotulo proprio
 * behemoth_widget_second_label, definido em res/values/behemoth.xml).
 *
 * onUpdate reescreve cada instancia com o layout widget_second.
 */
public class SecondAppWidget extends AppWidgetProvider {

    @Override
    public void onUpdate(Context context, AppWidgetManager appWidgetManager,
            int[] appWidgetIds) {
        for (int appWidgetId : appWidgetIds) {
            RemoteViews views = new RemoteViews(context.getPackageName(),
                    R.layout.widget_second);
            views.setTextViewText(R.id.widget_text,
                    context.getString(R.string.behemoth_widget_second_label));
            appWidgetManager.updateAppWidget(appWidgetId, views);
        }
    }
}
