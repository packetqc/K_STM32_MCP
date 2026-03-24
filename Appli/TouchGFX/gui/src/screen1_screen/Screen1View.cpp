#include <gui/screen1_screen/Screen1View.hpp>
#include <touchgfx/Color.hpp>
#include <touchgfx/canvas_widget_renderer/CanvasWidgetRenderer.hpp>

// Canvas widget renderer buffer (required for Circle and other canvas widgets)
static uint8_t canvasBuffer[3000];

Screen1View::Screen1View()
{
}

void Screen1View::setupScreen()
{
    Screen1ViewBase::setupScreen();

    // Initialize canvas widget renderer
    touchgfx::CanvasWidgetRenderer::setupBuffer(canvasBuffer, sizeof(canvasBuffer));

    // Blue circle, filled, centered on 800x480 display
    bluePainter.setColor(touchgfx::Color::getColorFromRGB(0, 100, 255));

    blueCircle.setPosition(200, 40, 400, 400);   // bounding box: x=200, y=40, w=400, h=400
    blueCircle.setCenter(200, 200);               // center relative to bounding box
    blueCircle.setRadius(190);                     // big circle, slight margin
    blueCircle.setLineWidth(0);                    // 0 = filled
    blueCircle.setArc(0, 360);                     // full circle
    blueCircle.setPainter(bluePainter);
    blueCircle.setPrecision(5);

    add(blueCircle);
}

void Screen1View::tearDownScreen()
{
    Screen1ViewBase::tearDownScreen();
}
