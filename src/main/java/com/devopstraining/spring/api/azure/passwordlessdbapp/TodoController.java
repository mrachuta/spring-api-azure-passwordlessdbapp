package com.devopstraining.spring.api.azure.passwordlessdbapp;

import java.util.HashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Value;
import java.util.concurrent.ThreadLocalRandom;

@RestController
@RequestMapping("/api")
public class TodoController {

    @Value("${STYLE_VERSION:v1}")
    private String styleVersion;

    @Value("${RANDOM_DELAYS:false}")
    private Boolean randomDelays;

    private final TodoRepository todoRepository;

    public TodoController(TodoRepository todoRepository) {
        this.todoRepository = todoRepository;
    }

    @PostMapping("/task")
    @ResponseStatus(HttpStatus.CREATED)
    public Todo createTodo(@RequestBody Todo todo) {
        return todoRepository.save(todo);
    }

    @GetMapping("/task")
    public Iterable<Todo> getTodos() {
        return todoRepository.findAll();
    }

    @GetMapping("/config")
    public Map<String, Object> getConfigurationAsJson() {
        if (randomDelays) {
            int sleepTime = ThreadLocalRandom.current().nextInt(1000, 10001);
            try {
                System.out.println("Sleeping for " + sleepTime + " milliseconds...");
                Thread.sleep(sleepTime);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                System.err.println("Sleep interrupted: " + e.getMessage());
            }
        }
        HashMap<String, Object> configMap = new HashMap<String, Object>();
        configMap.put("style_version", styleVersion);
        String tableStyle = (styleVersion.equals("v2")) ? "table-extra" : "table-standard";
        configMap.put("table_style", tableStyle);
        return configMap;
    }

    @GetMapping("/liveness")
    public Map<String, Object> getLivenessAsJson() {
        HashMap<String, Object> livenessMap = new HashMap<String, Object>();
        livenessMap.put("live", "true");
        return livenessMap;
    }

    @GetMapping("/readiness")
    public Map<String, Object> getReadinessAsJson() {
        HashMap<String, Object> readinessMap = new HashMap<String, Object>();
        readinessMap.put("ready", "true");
        return readinessMap;
    }
    
}
